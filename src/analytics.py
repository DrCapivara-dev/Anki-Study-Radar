from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from aqt import mw

from .config import get_config
from .radar import Recommendation, recommendations


@dataclass
class DailyActivity:
    day: date
    reviews: int = 0
    again: int = 0
    hard: int = 0
    good: int = 0
    easy: int = 0
    time_ms: int = 0

    @property
    def total(self) -> int:
        return self.again + self.hard + self.good + self.easy

    @property
    def retention(self) -> float | None:
        if self.total <= 0:
            return None
        return (self.hard + self.good + self.easy) / self.total


@dataclass
class AnalyticsSnapshot:
    recs: list[Recommendation]
    all_recs: list[Recommendation]
    activity_35d: list[DailyActivity]
    answer_counts_30d: dict[str, int]
    weekly_retention: list[tuple[str, float | None]]
    due_7d: list[tuple[str, int]]
    interval_buckets: list[tuple[str, int]]
    card_types: list[tuple[str, int]]
    tracked_topics: int
    attention_topics: int
    retention_30d: float | None
    current_streak: int
    active_days_30d: int
    reviews_30d: int
    due_total_7d: int
    estimated_minutes_7d: int
    average_interval_days: float
    longest_interval_days: int
    trend_7d: float | None


def _local_day_from_ms(ms: int) -> date:
    return datetime.fromtimestamp(ms / 1000).date()


def _activity(days: int = 35) -> list[DailyActivity]:
    days = max(1, min(730, int(days)))
    start = date.today() - timedelta(days=days - 1)
    cutoff_ms = int(datetime.combine(start, datetime.min.time()).timestamp() * 1000)
    rows = mw.col.db.all(
        """
        SELECT date(id / 1000, 'unixepoch', 'localtime') AS review_day,
               COUNT(*) AS reviews,
               SUM(CASE WHEN ease = 1 THEN 1 ELSE 0 END) AS again_count,
               SUM(CASE WHEN ease = 2 THEN 1 ELSE 0 END) AS hard_count,
               SUM(CASE WHEN ease = 3 THEN 1 ELSE 0 END) AS good_count,
               SUM(CASE WHEN ease = 4 THEN 1 ELSE 0 END) AS easy_count,
               SUM(CASE WHEN time > 60000 THEN 60000 ELSE time END) AS time_ms
        FROM revlog
        WHERE id >= ? AND ease BETWEEN 1 AND 4
        GROUP BY review_day
        ORDER BY review_day
        """,
        cutoff_ms,
    )
    mapped: dict[date, DailyActivity] = {}
    for day_text, reviews, again, hard, good, easy, time_ms in rows:
        if not day_text:
            continue
        try:
            d = datetime.strptime(str(day_text), "%Y-%m-%d").date()
        except Exception:
            continue
        mapped[d] = DailyActivity(
            day=d,
            reviews=int(reviews or 0),
            again=int(again or 0),
            hard=int(hard or 0),
            good=int(good or 0),
            easy=int(easy or 0),
            time_ms=int(time_ms or 0),
        )
    return [mapped.get(start + timedelta(days=i), DailyActivity(start + timedelta(days=i))) for i in range(days)]


def _answer_counts(activity: list[DailyActivity], days: int = 30) -> dict[str, int]:
    subset = activity[-max(1, int(days)):]
    return {
        "Again": sum(d.again for d in subset),
        "Hard": sum(d.hard for d in subset),
        "Good": sum(d.good for d in subset),
        "Easy": sum(d.easy for d in subset),
    }


def _retention_for_days(activity: list[DailyActivity], start_from_end: int, length: int) -> float | None:
    # start_from_end=0 means the most recent `length` days; 7 means the preceding week.
    end = len(activity) - start_from_end
    start = max(0, end - length)
    if end <= 0 or start >= end:
        return None
    subset = activity[start:end]
    total = sum(d.total for d in subset)
    if total <= 0:
        return None
    passed = sum(d.hard + d.good + d.easy for d in subset)
    return passed / total


def _weekly_retention(activity: list[DailyActivity]) -> list[tuple[str, float | None]]:
    labels = ["-4 sem", "-3 sem", "-2 sem", "Atual"]
    out: list[tuple[str, float | None]] = []
    # Oldest week first.
    for idx, label in enumerate(labels):
        start_from_end = (3 - idx) * 7
        out.append((label, _retention_for_days(activity, start_from_end, 7)))
    return out


def _current_streak(activity: list[DailyActivity]) -> int:
    active = {d.day for d in activity if d.reviews > 0}
    today = date.today()
    if today in active:
        cursor = today
    elif today - timedelta(days=1) in active:
        # Same convention many heatmaps use: a streak remains alive until the current day ends.
        cursor = today - timedelta(days=1)
    else:
        return 0
    streak = 0
    while cursor in active:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def _due_forecast(days: int = 7) -> list[tuple[str, int]]:
    days = max(1, min(30, int(days)))
    try:
        sched_today = int(mw.col.sched.today)
    except Exception:
        sched_today = 0
    labels = ["Hoje", "Amanhã", "D+2", "D+3", "D+4", "D+5", "D+6"]
    out: list[tuple[str, int]] = []
    for offset in range(days):
        due_day = sched_today + offset
        try:
            count = int(
                mw.col.db.scalar(
                    """
                    SELECT COUNT(*)
                    FROM cards
                    WHERE queue IN (2, 3)
                      AND (CASE WHEN odid != 0 THEN odue ELSE due END) = ?
                    """,
                    due_day,
                )
                or 0
            )
        except Exception:
            count = 0
        label = labels[offset] if offset < len(labels) else f"D+{offset}"
        out.append((label, count))
    return out


def _interval_buckets() -> tuple[list[tuple[str, int]], float, int]:
    try:
        rows = mw.col.db.all(
            """
            SELECT ivl
            FROM cards
            WHERE reps > 0 AND queue != -1 AND ivl > 0
            """
        )
    except Exception:
        rows = []
    values = [max(0, int(row[0] or 0)) for row in rows]
    buckets = [
        ("< 7 dias", sum(1 for v in values if v < 7)),
        ("7–30 dias", sum(1 for v in values if 7 <= v <= 30)),
        ("31–90 dias", sum(1 for v in values if 31 <= v <= 90)),
        ("> 90 dias", sum(1 for v in values if v > 90)),
    ]
    avg = (sum(values) / len(values)) if values else 0.0
    longest = max(values) if values else 0
    return buckets, avg, longest


def _card_types() -> list[tuple[str, int]]:
    try:
        row = mw.col.db.first(
            """
            SELECT
              SUM(CASE WHEN queue = 0 THEN 1 ELSE 0 END) AS unseen,
              SUM(CASE WHEN queue IN (1, 3) THEN 1 ELSE 0 END) AS learning,
              SUM(CASE WHEN queue >= 0 AND type = 2 AND ivl < 21 THEN 1 ELSE 0 END) AS young,
              SUM(CASE WHEN queue >= 0 AND type = 2 AND ivl >= 21 THEN 1 ELSE 0 END) AS mature,
              SUM(CASE WHEN queue < 0 THEN 1 ELSE 0 END) AS inactive
            FROM cards
            """
        ) or (0, 0, 0, 0, 0)
    except Exception:
        row = (0, 0, 0, 0, 0)
    unseen, learning, young, mature, inactive = [int(v or 0) for v in row]
    return [
        ("Maduros", mature),
        ("Jovens", young),
        ("Aprendendo", learning),
        ("Novos", unseen),
        ("Suspensos/ocultos", inactive),
    ]


def build_snapshot() -> AnalyticsSnapshot:
    cfg = get_config()
    recs = recommendations(include_hidden=False)
    all_recs = recommendations(include_hidden=True)
    activity = _activity(35)
    answers = _answer_counts(activity, 30)
    total_answers = sum(answers.values())
    retention = None if total_answers <= 0 else (answers["Hard"] + answers["Good"] + answers["Easy"]) / total_answers
    due = _due_forecast(7)
    buckets, avg_ivl, longest_ivl = _interval_buckets()
    card_types = _card_types()
    recent7 = _retention_for_days(activity, 0, 7)
    previous7 = _retention_for_days(activity, 7, 7)
    trend = None if recent7 is None or previous7 is None else recent7 - previous7
    due_total = sum(v for _label, v in due)
    seconds_per_card = max(10, min(120, int(cfg.get("focus_avg_seconds_per_card", 30))))
    est_minutes = round(due_total * seconds_per_card / 60)
    active30 = sum(1 for d in activity[-30:] if d.reviews > 0)
    reviews30 = sum(d.reviews for d in activity[-30:])
    attention = sum(1 for r in recs if r.days_until <= 0 or r.priority >= 80)
    return AnalyticsSnapshot(
        recs=recs,
        all_recs=all_recs,
        activity_35d=activity,
        answer_counts_30d=answers,
        weekly_retention=_weekly_retention(activity),
        due_7d=due,
        interval_buckets=buckets,
        card_types=card_types,
        tracked_topics=len(all_recs),
        attention_topics=attention,
        retention_30d=retention,
        current_streak=_current_streak(activity),
        active_days_30d=active30,
        reviews_30d=reviews30,
        due_total_7d=due_total,
        estimated_minutes_7d=est_minutes,
        average_interval_days=avg_ivl,
        longest_interval_days=longest_ivl,
        trend_7d=trend,
    )

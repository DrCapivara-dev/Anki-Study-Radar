from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import time
from typing import Any

from aqt import mw

from .config import get_config, normalized_intervals
from .licensing import has_pro_access


@dataclass
class Session:
    day: date
    reviews: int
    again: int
    hard: int
    good: int
    easy: int

    @property
    def struggle(self) -> float:
        return (self.again + 0.5 * self.hard) / self.reviews if self.reviews else 0.0

    @property
    def again_rate(self) -> float:
        return self.again / self.reviews if self.reviews else 0.0

    @property
    def hard_rate(self) -> float:
        return self.hard / self.reviews if self.reviews else 0.0

    @property
    def easy_rate(self) -> float:
        return self.easy / self.reviews if self.reviews else 0.0


@dataclass
class Recommendation:
    deck_id: int
    deck_name: str
    last_session: Session
    meaningful_sessions: int
    interval_days: int
    days_since: int
    days_until: int
    priority: int
    reason: str


def display_deck_name(name: str, mode: str | None = None) -> str:
    cfg = get_config()
    mode = mode or str(cfg.get("display_deck_names", "full"))
    parts = [part.strip() for part in name.split("::") if part.strip()]
    if not parts:
        return name
    if mode == "leaf":
        return parts[-1]
    if mode == "last2":
        return " › ".join(parts[-2:])
    return " › ".join(parts)


def deck_maps() -> tuple[dict[int, str], dict[int, int]]:
    names: dict[int, str] = {}
    for item in mw.col.decks.all_names_and_ids(include_filtered=False):
        names[int(item.id)] = str(item.name)

    counts: dict[int, int] = {}
    for did, count in mw.col.db.all(
        """
        SELECT CASE WHEN odid != 0 THEN odid ELSE did END AS target_did, COUNT(*)
        FROM cards
        GROUP BY target_did
        """
    ):
        counts[int(did)] = int(count)
    return names, counts


def session_rows(history_days: int) -> list[tuple[Any, ...]]:
    cutoff_ms = int((time.time() - history_days * 86400) * 1000)
    return mw.col.db.all(
        """
        SELECT CASE WHEN c.odid != 0 THEN c.odid ELSE c.did END AS target_did,
               date(r.id / 1000, 'unixepoch', 'localtime') AS review_day,
               COUNT(*) AS reviews,
               SUM(CASE WHEN r.ease = 1 THEN 1 ELSE 0 END) AS again_count,
               SUM(CASE WHEN r.ease = 2 THEN 1 ELSE 0 END) AS hard_count,
               SUM(CASE WHEN r.ease = 3 THEN 1 ELSE 0 END) AS good_count,
               SUM(CASE WHEN r.ease = 4 THEN 1 ELSE 0 END) AS easy_count
        FROM revlog r
        JOIN cards c ON c.id = r.cid
        WHERE r.id >= ? AND r.ease BETWEEN 1 AND 4
        GROUP BY target_did, review_day
        ORDER BY review_day DESC
        """,
        cutoff_ms,
    )


def _parse_day(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _performance_modifier(session: Session) -> float:
    struggle = session.struggle
    if struggle >= 0.35:
        return 0.60
    if struggle >= 0.22:
        return 0.75
    if struggle >= 0.12:
        return 0.90
    if session.easy_rate >= 0.35 and session.again_rate < 0.05:
        return 1.15
    return 1.0


def _exam_modifier(cfg: dict[str, Any]) -> float:
    if not has_pro_access() or not bool(cfg.get("exam_mode_enabled", False)):
        return 1.0
    raw = str(cfg.get("exam_date", "")).strip()
    try:
        exam = datetime.strptime(raw, "%Y-%m-%d").date()
    except Exception:
        return 1.0
    days = (exam - date.today()).days
    if days < 0:
        return 1.0
    if days <= 3:
        factor = 0.45
    elif days <= 7:
        factor = 0.55
    elif days <= 14:
        factor = 0.70
    elif days <= 30:
        factor = 0.85
    else:
        factor = 1.0
    intensity = max(1, min(3, int(cfg.get("exam_intensity", 2))))
    factor -= 0.05 * (intensity - 2)
    return max(0.35, min(1.0, factor))


def recommended_interval(session_count: int, session: Session, cfg: dict[str, Any]) -> int:
    intervals = normalized_intervals(cfg)
    base = intervals[min(max(session_count - 1, 0), len(intervals) - 1)]
    adjusted = round(base * _performance_modifier(session) * _exam_modifier(cfg))
    return max(1, min(730, adjusted))


def priority_score(days_until: int, session: Session, cfg: dict[str, Any]) -> int:
    if days_until <= 0:
        urgency = 72 + min(20, abs(days_until) * 5)
    else:
        urgency = max(10, 62 - days_until * 10)
    difficulty = min(18, round(session.struggle * 45))
    exam_boost = 0
    if has_pro_access() and bool(cfg.get("exam_mode_enabled", False)):
        exam_boost = 5
    return max(1, min(100, urgency + difficulty + exam_boost))


def _reason(days_until: int, session: Session) -> str:
    parts: list[str] = []
    if days_until < 0:
        parts.append(f"atrasado {abs(days_until)}d")
    elif days_until == 0:
        parts.append("vence hoje")
    else:
        parts.append(f"vence em {days_until}d")
    if session.again_rate >= 0.10:
        parts.append(f"Again {round(session.again_rate * 100)}%")
    if session.hard_rate >= 0.15:
        parts.append(f"Hard {round(session.hard_rate * 100)}%")
    if len(parts) == 1 and session.easy_rate >= 0.30:
        parts.append("bom desempenho")
    return " · ".join(parts)


def recommendations(include_hidden: bool = False) -> list[Recommendation]:
    cfg = get_config()
    history_days = max(1, int(cfg.get("history_days", 730)))
    minimum = max(1, int(cfg.get("minimum_session_reviews", 10)))
    ignored = {int(v) for v in cfg.get("ignored_deck_ids", []) if str(v).isdigit()}
    snoozed_raw = cfg.get("snoozed_until", {}) or {}
    snoozed: dict[int, date] = {}
    for key, value in snoozed_raw.items():
        try:
            snoozed[int(key)] = datetime.strptime(str(value), "%Y-%m-%d").date()
        except Exception:
            pass

    deck_names, card_counts = deck_maps()
    by_deck: dict[int, list[Session]] = {}
    for did, day_text, reviews, again, hard, good, easy in session_rows(history_days):
        did = int(did)
        if did not in deck_names or not day_text:
            continue
        threshold = min(minimum, max(1, card_counts.get(did, minimum)))
        if int(reviews) < threshold:
            continue
        by_deck.setdefault(did, []).append(
            Session(
                day=_parse_day(str(day_text)),
                reviews=int(reviews),
                again=int(again or 0),
                hard=int(hard or 0),
                good=int(good or 0),
                easy=int(easy or 0),
            )
        )

    today = date.today()
    out: list[Recommendation] = []
    for did, sessions in by_deck.items():
        if not include_hidden:
            if did in ignored:
                continue
            snooze_until = snoozed.get(did)
            if snooze_until and today < snooze_until:
                continue
        sessions.sort(key=lambda s: s.day, reverse=True)
        last = sessions[0]
        interval = recommended_interval(len(sessions), last, cfg)
        days_since = max(0, (today - last.day).days)
        days_until = interval - days_since
        out.append(
            Recommendation(
                deck_id=did,
                deck_name=deck_names[did],
                last_session=last,
                meaningful_sessions=len(sessions),
                interval_days=interval,
                days_since=days_since,
                days_until=days_until,
                priority=priority_score(days_until, last, cfg),
                reason=_reason(days_until, last),
            )
        )

    out.sort(key=lambda r: (r.days_until, -r.priority, r.deck_name.casefold()))
    return out

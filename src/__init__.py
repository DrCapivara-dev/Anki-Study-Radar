from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from html import escape
import math
import time
from typing import Any

from aqt import gui_hooks, mw
from aqt.deckbrowser import DeckBrowser
from aqt.utils import showInfo, tooltip

ADDON_NAME = "Anki Study Radar"
DEFAULT_CONFIG = {
    "history_days": 730,
    "max_rows": 8,
    "minimum_session_reviews": 5,
    "base_intervals_days": [2, 4, 7, 14, 21, 30, 45, 60],
    "show_upcoming_days": 5,
}


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
        if self.reviews <= 0:
            return 0.0
        return (self.again + 0.5 * self.hard) / self.reviews

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


def _display_deck_name(name: str) -> str:
    """Return a cleaner visual representation of Anki subdeck names."""
    parts = [part.strip() for part in name.split("::") if part.strip()]
    return " › ".join(parts) if parts else name


def _config() -> dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    try:
        user_cfg = mw.addonManager.getConfig(__name__) or {}
        cfg.update(user_cfg)
    except Exception:
        pass
    return cfg


def _parse_day(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _deck_maps() -> tuple[dict[int, str], dict[int, int]]:
    """Return deck-id -> name and deck-id -> direct/original card count."""
    names: dict[int, str] = {}
    for item in mw.col.decks.all_names_and_ids(include_filtered=False):
        names[int(item.id)] = str(item.name)

    counts: dict[int, int] = {}
    rows = mw.col.db.all(
        """
        SELECT CASE WHEN odid != 0 THEN odid ELSE did END AS target_did,
               COUNT(*)
        FROM cards
        GROUP BY target_did
        """
    )
    for did, count in rows:
        counts[int(did)] = int(count)
    return names, counts


def _session_rows(history_days: int) -> list[tuple[Any, ...]]:
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
        WHERE r.id >= ?
          AND r.ease BETWEEN 1 AND 4
        GROUP BY target_did, review_day
        ORDER BY review_day DESC
        """,
        cutoff_ms,
    )


def _performance_modifier(session: Session) -> float:
    """Smaller modifier = revisit sooner after a difficult session."""
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


def _recommended_interval(session_count: int, session: Session, cfg: dict[str, Any]) -> int:
    raw = cfg.get("base_intervals_days", DEFAULT_CONFIG["base_intervals_days"])
    intervals = [max(1, int(v)) for v in raw if int(v) > 0]
    if not intervals:
        intervals = list(DEFAULT_CONFIG["base_intervals_days"])
    base = intervals[min(max(session_count - 1, 0), len(intervals) - 1)]
    adjusted = round(base * _performance_modifier(session))
    return max(1, min(90, adjusted))


def _priority(days_until: int, session: Session) -> int:
    # Due/overdue decks dominate; poor performance adds urgency.
    if days_until <= 0:
        urgency = 72 + min(20, abs(days_until) * 5)
    else:
        urgency = max(10, 62 - days_until * 10)
    difficulty = min(18, round(session.struggle * 45))
    return max(1, min(100, urgency + difficulty))


def recommendations() -> list[Recommendation]:
    cfg = _config()
    history_days = int(cfg.get("history_days", 730))
    minimum = max(1, int(cfg.get("minimum_session_reviews", 5)))
    deck_names, card_counts = _deck_maps()

    by_deck: dict[int, list[Session]] = {}
    for did, day_text, reviews, again, hard, good, easy in _session_rows(history_days):
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
    result: list[Recommendation] = []
    for did, sessions in by_deck.items():
        sessions.sort(key=lambda s: s.day, reverse=True)
        last = sessions[0]
        session_count = len(sessions)
        interval = _recommended_interval(session_count, last, cfg)
        days_since = max(0, (today - last.day).days)
        days_until = interval - days_since
        result.append(
            Recommendation(
                deck_id=did,
                deck_name=deck_names[did],
                last_session=last,
                meaningful_sessions=session_count,
                interval_days=interval,
                days_since=days_since,
                days_until=days_until,
                priority=_priority(days_until, last),
            )
        )

    result.sort(key=lambda r: (r.days_until, -r.priority, r.deck_name.casefold()))
    return result


def _when_text(rec: Recommendation) -> tuple[str, str, str]:
    if rec.days_until < 0:
        n = abs(rec.days_until)
        return "ATRASADO", "radar-red", f"atrasado há {n} dia{'s' if n != 1 else ''}"
    if rec.days_until == 0:
        return "REVISAR HOJE", "radar-red", "revisão recomendada hoje"
    if rec.days_until == 1:
        return "AMANHÃ", "radar-yellow", "revisão sugerida amanhã"
    return "EM BREVE", "radar-green", f"revisão sugerida em {rec.days_until} dias"


def _ago_text(days: int) -> str:
    if days == 0:
        return "hoje"
    if days == 1:
        return "há 1 dia"
    return f"há {days} dias"


def _row_html(rec: Recommendation) -> str:
    label, color_class, timing = _when_text(rec)
    s = rec.last_session
    again_pct = round(s.again_rate * 100)
    hard_pct = round(s.hard_rate * 100)
    safe_name = escape(_display_deck_name(rec.deck_name))
    return f"""
    <div class="study-radar-row">
      <div class="study-radar-main">
        <div class="study-radar-name">{safe_name}</div>
        <div class="study-radar-meta">
          Última sessão {_ago_text(rec.days_since)} · {s.reviews} respostas · Again {again_pct}% · Hard {hard_pct}%
        </div>
      </div>
      <div class="study-radar-status">
        <span class="study-radar-pill {color_class}">{label}</span>
        <span class="study-radar-timing">{timing}</span>
      </div>
      <button class="study-radar-button" onclick="pycmd('study_radar:{rec.deck_id}')">Abrir baralho</button>
    </div>
    """


def _render_radar() -> str:
    try:
        recs = recommendations()
    except Exception as exc:
        return f"<div class='study-radar-card'><b>{ADDON_NAME}</b><br>Não foi possível calcular o radar: {escape(str(exc))}</div>"

    cfg = _config()
    show_upcoming = max(0, int(cfg.get("show_upcoming_days", 5)))
    max_rows = max(1, int(cfg.get("max_rows", 8)))

    visible = [r for r in recs if r.days_until <= show_upcoming][:max_rows]
    due = [r for r in recs if r.days_until <= 0]

    if due:
        headline = f"Hoje: {len(due)} baralho{'s' if len(due) != 1 else ''} merece{'m' if len(due) != 1 else ''} revisão"
        subtitle = f"Prioridade: <b>{escape(_display_deck_name(due[0].deck_name))}</b>. O radar não altera o FSRS; ele só recomenda quando revisitar o tema."
    elif recs:
        next_rec = recs[0]
        headline = "Nenhuma revisão temática está vencida hoje"
        if next_rec.days_until == 1:
            subtitle = f"Próxima sugestão: <b>{escape(_display_deck_name(next_rec.deck_name))}</b> amanhã."
        else:
            subtitle = f"Próxima sugestão: <b>{escape(_display_deck_name(next_rec.deck_name))}</b> em {next_rec.days_until} dias."
    else:
        headline = "Ainda não há histórico suficiente"
        subtitle = "Estude normalmente. Depois de uma sessão válida, o baralho começa a aparecer no Radar de Revisão."

    rows = "".join(_row_html(r) for r in visible)
    if not rows and recs:
        rows = "<div class='study-radar-empty'>Tudo em dia nos próximos dias.</div>"
    elif not rows:
        rows = "<div class='study-radar-empty'>O radar aparecerá aqui conforme você estudar seus baralhos.</div>"

    return f"""
    <style>
      .study-radar-card {{
        margin: 18px auto 14px auto;
        max-width: 980px;
        padding: 16px 18px;
        border: 1px solid rgba(128,128,128,.25);
        border-radius: 14px;
        background: rgba(128,128,128,.06);
        box-sizing: border-box;
      }}
      .study-radar-title {{ font-size: 19px; font-weight: 700; margin-bottom: 2px; }}
      .study-radar-subtitle {{ opacity: .78; margin-bottom: 12px; line-height: 1.35; }}
      .study-radar-row {{
        display: grid;
        grid-template-columns: minmax(260px,1fr) 170px 112px;
        gap: 12px;
        align-items: center;
        padding: 10px 0;
        border-top: 1px solid rgba(128,128,128,.16);
      }}
      .study-radar-name {{ font-weight: 650; font-size: 15px; overflow-wrap: anywhere; }}
      .study-radar-meta {{ font-size: 12px; opacity: .68; margin-top: 3px; }}
      .study-radar-status {{ display: flex; flex-direction: column; align-items: flex-start; gap: 3px; }}
      .study-radar-pill {{ display: inline-block; font-size: 11px; font-weight: 800; letter-spacing: .03em; padding: 4px 7px; border-radius: 999px; }}
      .radar-red {{ background: rgba(220,60,60,.17); color: #d94b4b; }}
      .radar-yellow {{ background: rgba(220,160,30,.17); color: #c28a13; }}
      .radar-green {{ background: rgba(45,160,95,.15); color: #32965c; }}
      .study-radar-timing {{ font-size: 11px; opacity: .65; }}
      .study-radar-button {{
        border: 1px solid rgba(90,120,220,.45);
        border-radius: 8px;
        padding: 7px 9px;
        cursor: pointer;
        font-weight: 600;
      }}
      .study-radar-empty {{ padding: 10px 0 2px 0; opacity: .65; }}
      @media (max-width: 720px) {{
        .study-radar-row {{ grid-template-columns: 1fr; gap: 7px; }}
        .study-radar-button {{ width: max-content; }}
      }}
    </style>
    <div class="study-radar-card">
      <div class="study-radar-title">🧠 {headline}</div>
      <div class="study-radar-subtitle">{subtitle}</div>
      {rows}
    </div>
    """


def on_deck_browser_will_render_content(deck_browser: DeckBrowser, content: Any) -> None:
    # Appending (instead of replacing) minimizes conflicts with other add-ons.
    content.stats += _render_radar()


def on_js_message(handled: tuple[bool, Any], message: str, context: Any) -> tuple[bool, Any]:
    if not message.startswith("study_radar:"):
        return handled

    try:
        did = int(message.split(":", 1)[1])
        if not mw.col.decks.name_if_exists(did):
            showInfo("Esse baralho não existe mais.", title=ADDON_NAME)
            return (True, None)
        mw.col.decks.select(did)
        mw.moveToState("overview")
        tooltip("Baralho aberto pelo Study Radar")
    except Exception as exc:
        showInfo(f"Não foi possível abrir o baralho.\n\n{exc}", title=ADDON_NAME)
    return (True, None)


gui_hooks.deck_browser_will_render_content.append(on_deck_browser_will_render_content)
gui_hooks.webview_did_receive_js_message.append(on_js_message)

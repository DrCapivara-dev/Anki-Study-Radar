from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from html import escape
import time
from typing import Any

from aqt import gui_hooks, mw
from aqt.deckbrowser import DeckBrowser
from aqt.qt import (
    QAction,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from aqt.utils import qconnect, showInfo, tooltip

ADDON_NAME = "Anki Study Radar"
VERSION = "0.3.0"
SMART_REVIEW_DECK_NAME = "Study Radar - Revisão Rápida"
DEFAULT_CONFIG = {
    "history_days": 730,
    "max_rows": 8,
    "minimum_session_reviews": 5,
    "base_intervals_days": [2, 4, 7, 14, 21, 30, 45, 60],
    "show_upcoming_days": 5,
    "smart_review_cards": 25,
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
    return max(1, min(730, adjusted))


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



def _smart_review_card_ids(deck_id: int, limit: int) -> list[int]:
    """Choose cards that are most useful for a short extra review.

    This intentionally favors lapses and recent Again/Hard answers. It does not
    change any scheduling state; the selected cards are later placed in a
    preview filtered deck.
    """
    limit = max(5, min(200, int(limit)))
    now_ms = int(time.time() * 1000)
    recent_cutoff_ms = now_ms - 90 * 86400 * 1000
    rows = mw.col.db.all(
        """
        SELECT c.id,
               c.lapses,
               c.reps,
               c.factor,
               c.ivl,
               SUM(CASE WHEN r.ease = 1 THEN 1 ELSE 0 END) AS again_total,
               SUM(CASE WHEN r.ease = 2 THEN 1 ELSE 0 END) AS hard_total,
               SUM(CASE WHEN r.ease = 1 AND r.id >= ? THEN 1 ELSE 0 END) AS recent_again,
               SUM(CASE WHEN r.ease = 2 AND r.id >= ? THEN 1 ELSE 0 END) AS recent_hard,
               MAX(r.id) AS last_review
        FROM cards c
        LEFT JOIN revlog r ON r.cid = c.id AND r.ease BETWEEN 1 AND 4
        WHERE (CASE WHEN c.odid != 0 THEN c.odid ELSE c.did END) = ?
          AND c.queue != -1
          AND c.reps > 0
        GROUP BY c.id
        """,
        recent_cutoff_ms,
        recent_cutoff_ms,
        deck_id,
    )

    scored: list[tuple[float, int]] = []
    for cid, lapses, reps, factor, ivl, again_total, hard_total, recent_again, recent_hard, last_review in rows:
        lapses = int(lapses or 0)
        reps = int(reps or 0)
        factor = int(factor or 0)
        ivl = int(ivl or 0)
        again_total = int(again_total or 0)
        hard_total = int(hard_total or 0)
        recent_again = int(recent_again or 0)
        recent_hard = int(recent_hard or 0)
        last_review = int(last_review or 0)

        days_since = (now_ms - last_review) / 86400000 if last_review else 365.0
        low_ease_bonus = max(0.0, (2500 - factor) / 250.0) if factor > 0 else 0.0
        # Recent failures matter most; historic lapses keep persistently difficult
        # cards high in the list. A small age bonus helps surface stale cards.
        score = (
            recent_again * 16.0
            + recent_hard * 7.0
            + lapses * 8.0
            + again_total * 2.5
            + hard_total * 1.0
            + low_ease_bonus
            + min(days_since, 120.0) / 20.0
            + min(ivl, 365) / 365.0
            + min(reps, 100) / 200.0
        )
        scored.append((score, int(cid)))

    scored.sort(key=lambda item: (-item[0], item[1]))
    return [cid for _score, cid in scored[:limit]]


def _existing_smart_review_deck_id() -> int:
    try:
        for item in mw.col.decks.all_names_and_ids(include_filtered=True):
            if str(item.name) == SMART_REVIEW_DECK_NAME:
                did = int(item.id)
                try:
                    if mw.col.decks.is_filtered(did):
                        return did
                except Exception:
                    return did
    except Exception:
        pass
    return 0


def start_smart_review(deck_id: int) -> None:
    """Build a preview filtered deck from the highest-priority cards."""
    if not mw.col.decks.name_if_exists(deck_id):
        showInfo("Esse baralho não existe mais.", title=ADDON_NAME)
        return

    cfg = _config()
    limit = max(5, min(200, int(cfg.get("smart_review_cards", 25))))
    try:
        cids = _smart_review_card_ids(deck_id, limit)
    except Exception as exc:
        showInfo(f"Não foi possível selecionar os cards da revisão rápida.\n\n{exc}", title=ADDON_NAME)
        return

    if not cids:
        showInfo(
            "Ainda não há cards revisados suficientes nesse baralho para montar uma Revisão Rápida.",
            title=ADDON_NAME,
        )
        return

    try:
        from anki.decks import DeckId, FilteredDeckConfig
        from aqt.operations import QueryOp
        from aqt.operations.scheduling import add_or_update_filtered_deck
    except Exception as exc:
        showInfo(
            "Sua versão do Anki não oferece a API necessária para a Revisão Rápida.\n\n"
            f"Atualize o Anki e tente novamente.\n\n{exc}",
            title=ADDON_NAME,
        )
        return

    existing_id = _existing_smart_review_deck_id()
    search = "cid:" + ",".join(str(cid) for cid in cids)
    source_name = _display_deck_name(mw.col.decks.name_if_exists(deck_id) or "Baralho")

    def got_deck(deck: Any) -> None:
        try:
            deck.name = SMART_REVIEW_DECK_NAME
            config = deck.config
            config.reschedule = False
            del config.delays[:]
            del config.search_terms[:]
            config.search_terms.extend(
                [
                    FilteredDeckConfig.SearchTerm(
                        search=search,
                        limit=len(cids),
                        order=FilteredDeckConfig.SearchTerm.Order.LAPSES,
                    )
                ]
            )
            # In preview mode: Again/Hard can repeat briefly, while Good returns
            # the card to its original deck. Normal FSRS scheduling is preserved.
            config.preview_again_secs = 60
            config.preview_hard_secs = 180
            config.preview_good_secs = 0
            deck.allow_empty = False

            def built(out: Any) -> None:
                try:
                    new_did = int(out.id)
                    mw.col.decks.select(new_did)
                    mw.moveToState("overview")
                    tooltip(f"Revisão rápida criada: {len(cids)} cards de {source_name}")
                except Exception as exc:
                    showInfo(f"A revisão foi criada, mas não foi possível abri-la.\n\n{exc}", title=ADDON_NAME)

            add_or_update_filtered_deck(parent=mw, deck=deck).success(built).failure(
                lambda exc: showInfo(f"Não foi possível montar a Revisão Rápida.\n\n{exc}", title=ADDON_NAME)
            ).run_in_background()
        except Exception as exc:
            showInfo(f"Não foi possível configurar a Revisão Rápida.\n\n{exc}", title=ADDON_NAME)

    QueryOp(
        parent=mw,
        op=lambda col: col.sched.get_or_create_filtered_deck(deck_id=DeckId(existing_id)),
        success=got_deck,
    ).failure(
        lambda exc: showInfo(f"Não foi possível preparar a Revisão Rápida.\n\n{exc}", title=ADDON_NAME)
    ).run_in_background()

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
          Última sessão {_ago_text(rec.days_since)} · {s.reviews} respostas · Again {again_pct}% · Hard {hard_pct}% · Prioridade {rec.priority}/100
        </div>
      </div>
      <div class="study-radar-status">
        <span class="study-radar-pill {color_class}">{label}</span>
        <span class="study-radar-timing">{timing}</span>
      </div>
      <div class="study-radar-actions">
        <button class="study-radar-button" onclick="pycmd('study_radar:{rec.deck_id}')">Abrir</button>
        <button class="study-radar-button study-radar-smart" onclick="pycmd('study_radar_smart:{rec.deck_id}')">⚡ Revisão rápida</button>
      </div>
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
      .study-radar-heading {{ display:flex; justify-content:space-between; gap:12px; align-items:flex-start; }}
      .study-radar-title {{ font-size: 19px; font-weight: 700; margin-bottom: 2px; }}
      .study-radar-subtitle {{ opacity: .78; margin-bottom: 12px; line-height: 1.35; }}
      .study-radar-settings {{
        border: 1px solid rgba(128,128,128,.3);
        border-radius: 8px;
        padding: 5px 9px;
        cursor: pointer;
        font-size: 12px;
        white-space: nowrap;
      }}
      .study-radar-row {{
        display: grid;
        grid-template-columns: minmax(260px,1fr) 170px 220px;
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
      .study-radar-actions {{ display:flex; gap:6px; justify-content:flex-end; flex-wrap:wrap; }}
      .study-radar-button {{
        border: 1px solid rgba(90,120,220,.45);
        border-radius: 8px;
        padding: 7px 9px;
        cursor: pointer;
        font-weight: 600;
      }}
      .study-radar-smart {{ font-weight: 700; }}
      .study-radar-empty {{ padding: 10px 0 2px 0; opacity: .65; }}
      @media (max-width: 720px) {{
        .study-radar-heading {{ flex-direction: column; }}
        .study-radar-row {{ grid-template-columns: 1fr; gap: 7px; }}
        .study-radar-actions {{ justify-content:flex-start; }}
        .study-radar-button {{ width: max-content; }}
      }}
    </style>
    <div class="study-radar-card">
      <div class="study-radar-heading">
        <div>
          <div class="study-radar-title">🧠 {headline}</div>
          <div class="study-radar-subtitle">{subtitle}</div>
        </div>
        <button class="study-radar-settings" onclick="pycmd('study_radar_settings')">⚙ Configurações</button>
      </div>
      {rows}
    </div>
    """


class StudyRadarSettingsDialog(QDialog):
    """Friendly GUI for editing Study Radar's config.json-backed settings."""

    def __init__(self) -> None:
        super().__init__(mw)
        self.setWindowTitle(f"{ADDON_NAME} — Configurações")
        self.setMinimumWidth(590)
        self.setMinimumHeight(500)
        self.setModal(False)

        root = QVBoxLayout(self)

        title = QLabel(f"<h2 style='margin-bottom:2px'>🧠 {ADDON_NAME}</h2><div>Configurações de revisão temática · v{VERSION}</div>")
        title.setWordWrap(True)
        root.addWidget(title)

        tabs = QTabWidget()
        root.addWidget(tabs, 1)

        # General tab
        general = QWidget()
        general_layout = QVBoxLayout(general)
        intro = QLabel(
            "Ajuste como o Radar escolhe e exibe os baralhos recomendados. "
            "Essas opções não alteram o FSRS nem os intervalos individuais dos cards."
        )
        intro.setWordWrap(True)
        general_layout.addWidget(intro)

        general_box = QGroupBox("Comportamento do Radar")
        form = QFormLayout(general_box)

        self.history_days = QSpinBox()
        self.history_days.setRange(30, 3650)
        self.history_days.setSuffix(" dias")
        self.history_days.setToolTip("Quantos dias do seu histórico de revisões o Radar pode analisar.")
        form.addRow("Histórico analisado:", self.history_days)

        self.max_rows = QSpinBox()
        self.max_rows.setRange(1, 50)
        self.max_rows.setSuffix(" baralhos")
        self.max_rows.setToolTip("Número máximo de baralhos mostrados no Radar da tela inicial.")
        form.addRow("Máximo exibido:", self.max_rows)

        self.minimum_session_reviews = QSpinBox()
        self.minimum_session_reviews.setRange(1, 500)
        self.minimum_session_reviews.setSuffix(" cards")
        self.minimum_session_reviews.setToolTip(
            "Mínimo de respostas no mesmo baralho e no mesmo dia para considerar uma sessão válida."
        )
        form.addRow("Sessão válida a partir de:", self.minimum_session_reviews)

        self.show_upcoming_days = QSpinBox()
        self.show_upcoming_days.setRange(0, 90)
        self.show_upcoming_days.setSuffix(" dias")
        self.show_upcoming_days.setToolTip("Quantos dias futuros de recomendações também devem aparecer.")
        form.addRow("Mostrar próximas revisões:", self.show_upcoming_days)

        general_layout.addWidget(general_box)
        general_layout.addStretch(1)
        tabs.addTab(general, "Geral")

        # Intervals tab
        intervals_page = QWidget()
        intervals_layout = QVBoxLayout(intervals_page)
        interval_help = QLabel(
            "Intervalos-base entre as revisões do baralho. O desempenho da última sessão pode "
            "encurtar ou aumentar levemente o intervalo automaticamente."
        )
        interval_help.setWordWrap(True)
        intervals_layout.addWidget(interval_help)

        interval_box = QGroupBox("Intervalos de revisão")
        interval_form = QFormLayout(interval_box)
        self.interval_boxes: list[QSpinBox] = []
        for index in range(len(DEFAULT_CONFIG["base_intervals_days"])):
            spin = QSpinBox()
            spin.setRange(1, 730)
            spin.setSuffix(" dias")
            spin.setToolTip(f"Intervalo-base após a {index + 1}ª sessão válida deste baralho.")
            self.interval_boxes.append(spin)
            interval_form.addRow(f"Após a {index + 1}ª sessão:", spin)
        intervals_layout.addWidget(interval_box)
        intervals_layout.addStretch(1)
        tabs.addTab(intervals_page, "Intervalos")

        # Smart Review tab
        smart = QWidget()
        smart_layout = QVBoxLayout(smart)
        smart_help = QLabel(
            "A Revisão Rápida monta uma sessão curta com os cards mais problemáticos do baralho, "
            "priorizando lapsos e respostas Again/Hard. Ela usa modo de pré-visualização e não "
            "altera o agendamento normal/FSRS dos cards."
        )
        smart_help.setWordWrap(True)
        smart_layout.addWidget(smart_help)

        smart_box = QGroupBox("Revisão Rápida")
        smart_form = QFormLayout(smart_box)
        self.smart_review_cards = QSpinBox()
        self.smart_review_cards.setRange(5, 200)
        self.smart_review_cards.setSuffix(" cards")
        self.smart_review_cards.setToolTip("Quantidade máxima de cards escolhidos para cada Revisão Rápida.")
        smart_form.addRow("Tamanho da sessão:", self.smart_review_cards)
        smart_layout.addWidget(smart_box)
        smart_layout.addStretch(1)
        tabs.addTab(smart, "Revisão Rápida")

        # About tab
        about = QWidget()
        about_layout = QVBoxLayout(about)
        about_text = QLabel(
            "<h3>Como funciona?</h3>"
            "<p>O Study Radar analisa suas sessões anteriores por baralho e recomenda quando "
            "revisitar aquele tema. Respostas <b>Again</b> e <b>Hard</b> tornam a recomendação "
            "mais urgente; bom desempenho permite espaçar.</p>"
            "<p><b>Revisão Rápida:</b> seleciona os cards mais problemáticos e os abre em um baralho "
            "filtrado de pré-visualização, sem alterar o agendamento normal/FSRS.</p>"
            "<p><b>Importante:</b> o Radar é uma camada de organização por tema. Ele não substitui "
            "o agendador do Anki.</p>"
            f"<p>Versão {VERSION}</p>"
        )
        about_text.setWordWrap(True)
        about_layout.addWidget(about_text)
        about_layout.addStretch(1)
        tabs.addTab(about, "Sobre")

        buttons = QHBoxLayout()
        self.reset_button = QPushButton("Restaurar padrões")
        self.close_button = QPushButton("Cancelar")
        self.save_button = QPushButton("Salvar")
        self.save_button.setDefault(True)
        buttons.addWidget(self.reset_button)
        buttons.addStretch(1)
        buttons.addWidget(self.close_button)
        buttons.addWidget(self.save_button)
        root.addLayout(buttons)

        qconnect(self.reset_button.clicked, self._load_defaults)
        qconnect(self.close_button.clicked, self.close)
        qconnect(self.save_button.clicked, self._save)

        self._load_current()

    def _apply_values(self, cfg: dict[str, Any]) -> None:
        self.history_days.setValue(int(cfg.get("history_days", DEFAULT_CONFIG["history_days"])))
        self.max_rows.setValue(int(cfg.get("max_rows", DEFAULT_CONFIG["max_rows"])))
        self.minimum_session_reviews.setValue(
            int(cfg.get("minimum_session_reviews", DEFAULT_CONFIG["minimum_session_reviews"]))
        )
        self.show_upcoming_days.setValue(
            int(cfg.get("show_upcoming_days", DEFAULT_CONFIG["show_upcoming_days"]))
        )
        self.smart_review_cards.setValue(
            int(cfg.get("smart_review_cards", DEFAULT_CONFIG["smart_review_cards"]))
        )

        raw = cfg.get("base_intervals_days", DEFAULT_CONFIG["base_intervals_days"])
        values = []
        try:
            values = [int(v) for v in raw]
        except Exception:
            values = []
        if not values:
            values = list(DEFAULT_CONFIG["base_intervals_days"])
        while len(values) < len(self.interval_boxes):
            values.append(values[-1])
        for spin, value in zip(self.interval_boxes, values):
            spin.setValue(max(1, min(730, int(value))))

    def _load_current(self) -> None:
        self._apply_values(_config())

    def _load_defaults(self) -> None:
        self._apply_values(DEFAULT_CONFIG)
        tooltip("Valores padrão carregados. Clique em Salvar para aplicar.")

    def _save(self) -> None:
        intervals = [spin.value() for spin in self.interval_boxes]
        if any(next_value < current for current, next_value in zip(intervals, intervals[1:])):
            showInfo(
                "Os intervalos não podem diminuir de uma etapa para a seguinte.\n\n"
                "Exemplo válido: 2, 4, 7, 14, 21...",
                title=ADDON_NAME,
            )
            return

        # Preserve any future/unknown keys that may already exist.
        try:
            cfg = mw.addonManager.getConfig(__name__) or {}
        except Exception:
            cfg = {}
        cfg.update(
            {
                "history_days": self.history_days.value(),
                "max_rows": self.max_rows.value(),
                "minimum_session_reviews": self.minimum_session_reviews.value(),
                "show_upcoming_days": self.show_upcoming_days.value(),
                "smart_review_cards": self.smart_review_cards.value(),
                "base_intervals_days": intervals,
            }
        )

        try:
            mw.addonManager.writeConfig(__name__, cfg)
        except Exception as exc:
            showInfo(f"Não foi possível salvar as configurações.\n\n{exc}", title=ADDON_NAME)
            return

        tooltip("Configurações do Study Radar salvas")
        try:
            if getattr(mw, "state", "") == "deckBrowser":
                mw.deckBrowser.refresh()
        except Exception:
            pass
        self.close()


def open_settings_dialog() -> None:
    """Open or focus the friendly Study Radar settings window."""
    existing = getattr(mw, "_study_radar_settings_dialog", None)
    try:
        if existing is not None and existing.isVisible():
            existing.raise_()
            existing.activateWindow()
            return
    except Exception:
        pass

    dialog = StudyRadarSettingsDialog()
    mw._study_radar_settings_dialog = dialog
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()


def on_deck_browser_will_render_content(deck_browser: DeckBrowser, content: Any) -> None:
    # Appending (instead of replacing) minimizes conflicts with other add-ons.
    content.stats += _render_radar()


def on_js_message(handled: tuple[bool, Any], message: str, context: Any) -> tuple[bool, Any]:
    if message == "study_radar_settings":
        open_settings_dialog()
        return (True, None)

    if message.startswith("study_radar_smart:"):
        try:
            did = int(message.split(":", 1)[1])
            start_smart_review(did)
        except Exception as exc:
            showInfo(f"Não foi possível iniciar a Revisão Rápida.\n\n{exc}", title=ADDON_NAME)
        return (True, None)

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


# Hooks used by the Radar itself.
gui_hooks.deck_browser_will_render_content.append(on_deck_browser_will_render_content)
gui_hooks.webview_did_receive_js_message.append(on_js_message)

# Friendly settings shortcut under Anki's Tools menu.
settings_action = QAction("Study Radar Settings...", mw)
qconnect(settings_action.triggered, open_settings_dialog)
mw.form.menuTools.addAction(settings_action)

from __future__ import annotations

import time
from typing import Any

from aqt import mw
from aqt.qt import QTimer
from aqt.utils import showInfo, tooltip

from .constants import ADDON_NAME, FOCUS_REVIEW_DECK_NAME, SMART_REVIEW_DECK_NAME, TEMP_DECK_PREFIX
from .config import get_config
from .radar import Recommendation, display_deck_name, recommendations



def _is_study_radar_temp_deck(deck_id: int) -> bool:
    try:
        name = mw.col.decks.name_if_exists(deck_id) or ""
        return bool(name.startswith(TEMP_DECK_PREFIX) and mw.col.decks.is_filtered(deck_id))
    except Exception:
        return False


def _cards_currently_in_filtered_deck(deck_id: int) -> int:
    try:
        return int(mw.col.db.scalar("SELECT COUNT(*) FROM cards WHERE did = ?", deck_id) or 0)
    except Exception:
        return 0


def _fallback_normal_deck(preferred_id: int = 0, excluding: int = 0) -> int:
    try:
        if preferred_id and preferred_id != excluding and mw.col.decks.name_if_exists(preferred_id):
            if not mw.col.decks.is_filtered(preferred_id):
                return int(preferred_id)
    except Exception:
        pass
    try:
        for item in mw.col.decks.all_names_and_ids(include_filtered=False):
            did = int(item.id)
            if did != excluding:
                return did
    except Exception:
        pass
    return 1


def _remove_empty_temp_deck(deck_id: int, fallback_deck_id: int = 0, announce: bool = False) -> bool:
    if not _is_study_radar_temp_deck(deck_id):
        return False
    if _cards_currently_in_filtered_deck(deck_id) != 0:
        return False
    try:
        from anki.decks import DeckId
        selected = int(mw.col.decks.selected())
        if selected == deck_id:
            fallback = _fallback_normal_deck(fallback_deck_id, excluding=deck_id)
            if mw.col.decks.name_if_exists(fallback):
                mw.col.decks.select(fallback)
        mw.col.decks.remove([DeckId(deck_id)])
        if announce:
            tooltip("Sessão concluída — baralho temporário removido")
        return True
    except Exception:
        return False


def cleanup_empty_temporary_decks(*, announce: bool = False) -> int:
    """Remove only empty filtered decks created by Study Radar."""
    try:
        if getattr(mw, "col", None) is None:
            return 0
        if getattr(mw, "state", "") == "review":
            return 0
        candidates: list[int] = []
        for item in mw.col.decks.all_names_and_ids(include_filtered=True):
            did = int(item.id)
            name = str(item.name)
            if name.startswith(TEMP_DECK_PREFIX):
                try:
                    if mw.col.decks.is_filtered(did) and _cards_currently_in_filtered_deck(did) == 0:
                        candidates.append(did)
                except Exception:
                    continue
        removed = 0
        for did in candidates:
            if _remove_empty_temp_deck(did):
                removed += 1
        if removed and announce:
            tooltip(f"{removed} sessão{'ões' if removed != 1 else ''} temporária{'s' if removed != 1 else ''} removida{'s' if removed != 1 else ''}")
        try:
            if removed and getattr(mw, "state", "") == "deckBrowser":
                mw.deckBrowser.refresh()
        except Exception:
            pass
        return removed
    except Exception:
        return 0


def schedule_cleanup_after_answer(card: Any) -> None:
    """Delete a Study Radar filtered deck after its final card leaves it."""
    cfg = get_config()
    if not bool(cfg.get("auto_cleanup_temp_decks", True)):
        return
    try:
        selected = int(mw.col.decks.selected())
        if not _is_study_radar_temp_deck(selected):
            return
        fallback = int(getattr(card, "did", 0) or 0)
    except Exception:
        return

    def attempt(tries: int = 0) -> None:
        try:
            if not _is_study_radar_temp_deck(selected):
                return
            if _cards_currently_in_filtered_deck(selected) != 0:
                return
            # Give Anki time to leave the reviewer before deleting its selected deck.
            if getattr(mw, "state", "") == "review" and tries < 8:
                QTimer.singleShot(250, lambda: attempt(tries + 1))
                return
            if getattr(mw, "state", "") == "review":
                return
            if _remove_empty_temp_deck(selected, fallback_deck_id=fallback, announce=True):
                if getattr(mw, "state", "") == "overview":
                    mw.moveToState("deckBrowser")
                elif getattr(mw, "state", "") == "deckBrowser":
                    try:
                        mw.deckBrowser.refresh()
                    except Exception:
                        pass
        except Exception:
            return

    QTimer.singleShot(300, attempt)


def smart_card_candidates(deck_id: int, limit: int = 200) -> list[tuple[float, int]]:
    limit = max(5, min(1000, int(limit)))
    now_ms = int(time.time() * 1000)
    recent_cutoff_ms = now_ms - 90 * 86400 * 1000
    rows = mw.col.db.all(
        """
        SELECT c.id, c.lapses, c.reps, c.factor, c.ivl,
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
        score = (
            recent_again * 16.0 + recent_hard * 7.0 + lapses * 8.0 +
            again_total * 2.5 + hard_total * 1.0 + low_ease_bonus +
            min(days_since, 120.0) / 20.0 + min(ivl, 365) / 365.0 + min(reps, 100) / 200.0
        )
        scored.append((score, int(cid)))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return scored[:limit]


def start_smart_review(deck_id: int) -> None:
    if not mw.col.decks.name_if_exists(deck_id):
        showInfo("Esse baralho não existe mais.", title=ADDON_NAME)
        return
    cfg = get_config()
    limit = max(5, min(200, int(cfg.get("smart_review_cards", 25))))
    candidates = smart_card_candidates(deck_id, limit)
    if not candidates:
        showInfo("Ainda não há cards revisados suficientes nesse baralho.", title=ADDON_NAME)
        return
    cids = [cid for _score, cid in candidates]
    source = display_deck_name(mw.col.decks.name_if_exists(deck_id) or "Baralho")
    create_preview_filtered_deck(SMART_REVIEW_DECK_NAME, cids, f"{len(cids)} cards de {source}")


def build_focus_card_ids(minutes: int) -> list[int]:
    cfg = get_config()
    seconds = max(10, min(120, int(cfg.get("focus_avg_seconds_per_card", 30))))
    target = max(10, min(250, round(minutes * 60 / seconds)))
    recs = recommendations()
    combined: list[tuple[float, int]] = []
    for rec in recs[:20]:
        # Fetch extra cards per deck, then combine deck urgency with card difficulty.
        for score, cid in smart_card_candidates(rec.deck_id, min(100, target)):
            combined.append((score + rec.priority * 2.0, cid))
    combined.sort(key=lambda item: (-item[0], item[1]))
    seen: set[int] = set()
    result: list[int] = []
    for _score, cid in combined:
        if cid in seen:
            continue
        seen.add(cid)
        result.append(cid)
        if len(result) >= target:
            break
    return result


def start_focus_review(minutes: int) -> None:
    cids = build_focus_card_ids(minutes)
    if not cids:
        showInfo("Não encontrei cards revisados suficientes para montar a Sessão Foco.", title=ADDON_NAME)
        return
    create_preview_filtered_deck(FOCUS_REVIEW_DECK_NAME, cids, f"Sessão Foco de ~{minutes} min ({len(cids)} cards)")


def _existing_filtered_deck_id(name: str) -> int:
    try:
        for item in mw.col.decks.all_names_and_ids(include_filtered=True):
            if str(item.name) == name:
                did = int(item.id)
                try:
                    if mw.col.decks.is_filtered(did):
                        return did
                except Exception:
                    return did
    except Exception:
        pass
    return 0


def create_preview_filtered_deck(name: str, cids: list[int], label: str) -> None:
    try:
        from anki.decks import DeckId, FilteredDeckConfig
        from aqt.operations import QueryOp
        from aqt.operations.scheduling import add_or_update_filtered_deck
    except Exception as exc:
        showInfo(
            "Sua versão do Anki não oferece a API necessária para as sessões inteligentes.\n\n"
            f"Atualize o Anki e tente novamente.\n\n{exc}",
            title=ADDON_NAME,
        )
        return

    existing_id = _existing_filtered_deck_id(name)
    search = "cid:" + ",".join(str(cid) for cid in cids)

    def got_deck(deck: Any) -> None:
        try:
            deck.name = name
            config = deck.config
            config.reschedule = False
            del config.delays[:]
            del config.search_terms[:]
            config.search_terms.extend([
                FilteredDeckConfig.SearchTerm(
                    search=search,
                    limit=len(cids),
                    order=FilteredDeckConfig.SearchTerm.Order.LAPSES,
                )
            ])
            config.preview_again_secs = 60
            config.preview_hard_secs = 180
            config.preview_good_secs = 0
            deck.allow_empty = False

            def built(out: Any) -> None:
                try:
                    new_did = int(out.id)
                    mw.col.decks.select(new_did)
                    mw.moveToState("overview")
                    tooltip(f"{label}")
                except Exception as exc:
                    showInfo(f"A sessão foi criada, mas não foi possível abri-la.\n\n{exc}", title=ADDON_NAME)

            add_or_update_filtered_deck(parent=mw, deck=deck).success(built).failure(
                lambda exc: showInfo(f"Não foi possível montar a sessão.\n\n{exc}", title=ADDON_NAME)
            ).run_in_background()
        except Exception as exc:
            showInfo(f"Não foi possível configurar a sessão.\n\n{exc}", title=ADDON_NAME)

    QueryOp(
        parent=mw,
        op=lambda col: col.sched.get_or_create_filtered_deck(deck_id=DeckId(existing_id)),
        success=got_deck,
    ).failure(
        lambda exc: showInfo(f"Não foi possível preparar a sessão.\n\n{exc}", title=ADDON_NAME)
    ).run_in_background()

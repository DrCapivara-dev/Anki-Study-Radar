from __future__ import annotations

from typing import Any

from aqt import gui_hooks, mw
from aqt.deckbrowser import DeckBrowser
from aqt.qt import QAction, QTimer
from aqt.utils import qconnect, showInfo, tooltip

from .config import PACKAGE
from .constants import ADDON_NAME
from .licensing import (
    account_status,
    activate_account_device,
    activate_checkout_license,
    check_checkout_status,
    checkout_state,
    has_pro_access,
    license_status,
    migrate_environment_state,
    refresh_account,
    verify_license,
)
from .review import cleanup_empty_temporary_decks, schedule_cleanup_after_answer, start_smart_review
from .ui import ignore_deck, open_analytics_dialog, open_focus_dialog, open_main_dialog, open_pro_settings, open_settings_dialog, snooze_deck
from .webui import render_radar


def _on_deck_browser(deck_browser: DeckBrowser, content: Any) -> None:
    content.stats += render_radar()


def _on_js_message(handled: tuple[bool, Any], message: str, context: Any) -> tuple[bool, Any]:
    try:
        if message == "sr_settings":
            open_settings_dialog(); return (True, None)
        if message == "sr_license":
            open_pro_settings(); return (True, None)
        if message == "sr_focus":
            open_focus_dialog(); return (True, None)
        if message == "sr_analytics":
            open_analytics_dialog(); return (True, None)
        if message.startswith("sr_open:"):
            did = int(message.split(":",1)[1])
            if not mw.col.decks.name_if_exists(did): showInfo("Esse baralho não existe mais.", title=ADDON_NAME); return (True,None)
            mw.col.decks.select(did); mw.moveToState("overview"); tooltip("Baralho aberto pelo Study Radar"); return (True,None)
        if message.startswith("sr_smart:"):
            start_smart_review(int(message.split(":",1)[1])); return (True,None)
        if message.startswith("sr_snooze:"):
            snooze_deck(int(message.split(":",1)[1])); return (True,None)
        if message.startswith("sr_ignore:"):
            ignore_deck(int(message.split(":",1)[1])); return (True,None)
    except Exception as exc:
        showInfo(f"O Study Radar encontrou um erro.\n\n{exc}", title=ADDON_NAME)
        return (True, None)
    return handled


def _on_reviewer_answered(reviewer: Any, card: Any, ease: int) -> None:
    schedule_cleanup_after_answer(card)


def _resume_license_tasks() -> None:
    """Resume purchases, account sessions and commercial activations."""
    try:
        if not has_pro_access() and checkout_state().get("session_token"):
            def task():
                ok, data = check_checkout_status()
                if ok and isinstance(data, dict) and data.get("status") == "approved":
                    return ("purchase",) + activate_checkout_license(data)
                return ("pending", ok, data)

            def done(future):
                try:
                    result = future.result()
                    if result and result[0] == "purchase" and result[1]:
                        tooltip("⭐ Pagamento confirmado: Study Radar Pro ativado")
                        try:
                            if getattr(mw, "state", "") == "deckBrowser":
                                mw.deckBrowser.refresh()
                        except Exception:
                            pass
                except Exception:
                    pass

            mw.taskman.run_in_background(task, done)
            return

        acct = account_status()
        if acct.logged_in:
            def account_task():
                ok, _ = refresh_account()
                if ok and account_status().has_pro and not has_pro_access():
                    return activate_account_device()
                return (ok, "")
            def account_done(future):
                try:
                    future.result()
                except Exception:
                    pass
            mw.taskman.run_in_background(account_task, account_done)

        status = license_status()
        if status.active and status.role in {"PRO", "TESTER"}:
            def verify_done(future):
                try:
                    future.result()
                except Exception:
                    pass
            mw.taskman.run_in_background(verify_license, verify_done)
    except Exception:
        pass


def _on_profile_opened() -> None:
    try:
        from .config import get_config
        migrated = migrate_environment_state()
        if migrated:
            tooltip("Study Radar atualizado para o ambiente de produção. Entre novamente na sua conta.")
        if bool(get_config().get("cleanup_temp_on_startup", True)):
            QTimer.singleShot(800, lambda: cleanup_empty_temporary_decks(announce=False))
        QTimer.singleShot(1400, _resume_license_tasks)
    except Exception:
        pass



def _register_menu() -> None:
    action = QAction("Study Radar", mw)
    qconnect(action.triggered, open_main_dialog)
    mw.form.menuTools.addAction(action)


gui_hooks.deck_browser_will_render_content.append(_on_deck_browser)
gui_hooks.webview_did_receive_js_message.append(_on_js_message)
gui_hooks.reviewer_did_answer_card.append(_on_reviewer_answered)
gui_hooks.profile_did_open.append(_on_profile_opened)
_register_menu()

# Clicking Config in Anki's Add-ons window opens our friendly settings dialog.
try:
    mw.addonManager.setConfigAction(PACKAGE, open_settings_dialog)
except Exception:
    pass

ADDON_NAME = "Anki Study Radar"
VERSION = "1.3.0"
SMART_REVIEW_DECK_NAME = "Study Radar - Revisão Rápida"
FOCUS_REVIEW_DECK_NAME = "Study Radar - Sessão Foco"
TEMP_DECK_PREFIX = "Study Radar - "
LICENSE_API_URL = "https://study-radar-backend.onrender.com"
OWNER_KEY_HASH = "f6a374eba54f440e609beba30a28b1dd825cc678c4415edfcdcd464d758c44b7"

DEFAULT_CONFIG = {
    "history_days": 730,
    "max_rows": 10,
    "minimum_session_reviews": 10,
    "base_intervals_days": [2, 4, 7, 14, 21, 30, 45, 60],
    "show_upcoming_days": 7,
    "smart_review_cards": 25,
    "display_deck_names": "full",
    "ignored_deck_ids": [],
    "snoozed_until": {},
    "show_reasons": True,
    "focus_avg_seconds_per_card": 30,
    "exam_mode_enabled": False,
    "exam_date": "",
    "exam_intensity": 2,
    "license_api_url": LICENSE_API_URL,
    "auto_cleanup_temp_decks": True,
    "cleanup_temp_on_startup": True,
}

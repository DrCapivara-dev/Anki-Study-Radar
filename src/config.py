from __future__ import annotations

from typing import Any
from aqt import mw

from .constants import DEFAULT_CONFIG

PACKAGE = __package__ or __name__.split(".")[0]


def get_config() -> dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    try:
        user_cfg = mw.addonManager.getConfig(PACKAGE) or {}
        cfg.update(user_cfg)
    except Exception:
        pass
    return cfg


def write_config(cfg: dict[str, Any]) -> None:
    mw.addonManager.writeConfig(PACKAGE, cfg)


def update_config(**changes: Any) -> dict[str, Any]:
    cfg = get_config()
    cfg.update(changes)
    write_config(cfg)
    return cfg


def normalized_intervals(cfg: dict[str, Any] | None = None) -> list[int]:
    cfg = cfg or get_config()
    raw = cfg.get("base_intervals_days", DEFAULT_CONFIG["base_intervals_days"])
    vals: list[int] = []
    try:
        vals = [max(1, min(730, int(v))) for v in raw]
    except Exception:
        vals = []
    if not vals:
        vals = list(DEFAULT_CONFIG["base_intervals_days"])
    while len(vals) < len(DEFAULT_CONFIG["base_intervals_days"]):
        vals.append(vals[-1])
    return vals[: len(DEFAULT_CONFIG["base_intervals_days"])]

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
USER_FILES = BASE_DIR / "user_files"
USER_FILES.mkdir(exist_ok=True)


def _read_json(name: str, default: Any) -> Any:
    path = USER_FILES / name
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(name: str, data: Any) -> None:
    path = USER_FILES / name
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _clear(name: str) -> None:
    path = USER_FILES / name
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def read_license_state() -> dict[str, Any]:
    return _read_json("license_state.json", {})


def write_license_state(data: dict[str, Any]) -> None:
    _write_json("license_state.json", data)


def clear_license_state() -> None:
    _clear("license_state.json")


def read_device_state() -> dict[str, Any]:
    return _read_json("device.json", {})


def write_device_state(data: dict[str, Any]) -> None:
    _write_json("device.json", data)


def read_checkout_state() -> dict[str, Any]:
    return _read_json("checkout_state.json", {})


def write_checkout_state(data: dict[str, Any]) -> None:
    _write_json("checkout_state.json", data)


def clear_checkout_state() -> None:
    _clear("checkout_state.json")


def read_account_state() -> dict[str, Any]:
    return _read_json("account_state.json", {})


def write_account_state(data: dict[str, Any]) -> None:
    _write_json("account_state.json", data)


def clear_account_state() -> None:
    _clear("account_state.json")

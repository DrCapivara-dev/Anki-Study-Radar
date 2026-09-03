from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import platform
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any

from .config import get_config
from .constants import LICENSE_API_URL, OWNER_KEY_HASH, VERSION
from .storage import (
    clear_account_state,
    clear_checkout_state,
    clear_license_state,
    read_account_state,
    read_checkout_state,
    read_device_state,
    read_license_state,
    write_account_state,
    write_checkout_state,
    write_device_state,
    write_license_state,
)

VALID_ROLES = {"OWNER", "PRO", "TESTER"}


@dataclass
class LicenseStatus:
    active: bool
    role: str = "FREE"
    label: str = "Free"
    detail: str = "Recursos gratuitos ativos"
    plan: str = ""
    active_devices: int | None = None
    max_devices: int | None = None


@dataclass
class AccountStatus:
    logged_in: bool
    email: str = ""
    has_pro: bool = False
    role: str = "FREE"
    plan: str = ""
    active_devices: int = 0
    max_devices: int = 1


def normalize_key(value: str) -> str:
    return "-".join(part for part in value.strip().upper().replace(" ", "").split("-") if part)


def device_id() -> str:
    state = read_device_state()
    value = str(state.get("device_id", "")).strip()
    if value:
        return value
    value = str(uuid.uuid4())
    write_device_state({"device_id": value, "created_at": _now_iso()})
    return value


def device_name() -> str:
    name = (platform.node() or "Meu computador").strip()
    return name[:150]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _key_hash(key: str) -> str:
    return hashlib.sha256(normalize_key(key).encode("utf-8")).hexdigest()


def _api_url() -> str:
    configured = str(get_config().get("license_api_url", "")).strip().rstrip("/")
    return configured or LICENSE_API_URL.rstrip("/")


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except Exception:
        return None


# ----------------------------- Local status --------------------------------
def account_status() -> AccountStatus:
    state = read_account_state()
    token = str(state.get("account_token", "")).strip()
    email = str(state.get("email", "")).strip()
    if not token or not email:
        return AccountStatus(False)
    return AccountStatus(
        True,
        email=email,
        has_pro=bool(state.get("has_pro", False)),
        role=str(state.get("role", "FREE")).upper(),
        plan=str(state.get("plan", "")),
        active_devices=int(state.get("active_devices") or 0),
        max_devices=int(state.get("max_devices") or 1),
    )


def license_status() -> LicenseStatus:
    state = read_license_state()
    role = str(state.get("role", "FREE")).upper()
    if role not in VALID_ROLES or str(state.get("status", "")).lower() != "active":
        return LicenseStatus(False)
    if str(state.get("device_id", "")) != device_id():
        return LicenseStatus(False, detail="Licença vinculada a outro dispositivo")
    # Account-based commercial access requires a locally logged-in account.
    if str(state.get("source", "")) == "account" and not account_status().logged_in:
        return LicenseStatus(False, detail="Entre novamente na sua conta Study Radar")

    plan = str(state.get("plan", ""))
    active_devices = _optional_int(state.get("active_devices"))
    max_devices = _optional_int(state.get("max_devices"))
    suffix = ""
    if active_devices is not None and max_devices is not None:
        suffix = f" · dispositivo {active_devices}/{max_devices}"

    if role == "OWNER":
        return LicenseStatus(True, "OWNER", "Owner", "Acesso total do proprietário", plan, active_devices, max_devices)
    if role == "TESTER":
        return LicenseStatus(True, "TESTER", "Tester Pro", f"Licença de testes ativa{suffix}", plan, active_devices, max_devices)
    return LicenseStatus(True, "PRO", "Pro", f"Study Radar Pro ativo{suffix}", plan, active_devices, max_devices)


def has_pro_access() -> bool:
    return license_status().active


# ----------------------------- Accounts ------------------------------------
def _save_account_response(data: dict[str, Any]) -> None:
    write_account_state(
        {
            "account_token": str(data.get("account_token", read_account_state().get("account_token", ""))),
            "email": str(data.get("email", read_account_state().get("email", ""))),
            "has_pro": bool(data.get("has_pro", False)),
            "role": str(data.get("role", "FREE")).upper(),
            "plan": str(data.get("plan", "")),
            "active_devices": int(data.get("active_devices") or 0),
            "max_devices": int(data.get("max_devices") or 1),
            "last_checked_at": _now_iso(),
        }
    )


def register_account(email: str, password: str) -> tuple[bool, str]:
    ok, data = _request_json("POST", f"{_api_url()}/v1/accounts/register", {"email": email.strip(), "password": password}, timeout=30)
    if not ok:
        return False, str(data)
    payload = data if isinstance(data, dict) else {}
    if not payload.get("account_token"):
        return False, "O servidor não retornou uma sessão de conta válida."
    _save_account_response(payload)
    return True, "Conta criada e conectada."


def login_account(email: str, password: str) -> tuple[bool, str]:
    ok, data = _request_json("POST", f"{_api_url()}/v1/accounts/login", {"email": email.strip(), "password": password}, timeout=30)
    if not ok:
        return False, str(data)
    payload = data if isinstance(data, dict) else {}
    if not payload.get("account_token"):
        return False, "O servidor não retornou uma sessão de conta válida."
    _save_account_response(payload)
    return True, "Login realizado com sucesso."


def refresh_account() -> tuple[bool, str]:
    state = read_account_state()
    token = str(state.get("account_token", "")).strip()
    if not token:
        return False, "Nenhuma conta conectada."
    ok, data = _request_json("POST", f"{_api_url()}/v1/accounts/me", {"account_token": token}, timeout=20)
    if not ok:
        return False, str(data)
    payload = data if isinstance(data, dict) else {}
    payload["account_token"] = token
    _save_account_response(payload)
    return True, "Conta atualizada."


def logout_account() -> tuple[bool, str]:
    state = read_account_state()
    token = str(state.get("account_token", "")).strip()
    if token:
        _request_json("POST", f"{_api_url()}/v1/accounts/logout", {"account_token": token}, timeout=15)
    lic = read_license_state()
    if str(lic.get("source", "")) == "account":
        clear_license_state()
    clear_account_state()
    clear_checkout_state()
    return True, "Você saiu da conta Study Radar neste Anki."


def change_account_password(current_password: str, new_password: str) -> tuple[bool, str]:
    token = str(read_account_state().get("account_token", "")).strip()
    if not token:
        return False, "Entre na sua conta primeiro."
    ok, data = _request_json(
        "POST", f"{_api_url()}/v1/accounts/change-password",
        {"account_token": token, "current_password": current_password, "new_password": new_password}, timeout=25,
    )
    return (True, "Senha alterada com sucesso.") if ok else (False, str(data))


def activate_account_device() -> tuple[bool, str]:
    acct = read_account_state()
    token = str(acct.get("account_token", "")).strip()
    if not token:
        return False, "Entre na sua conta Study Radar primeiro."
    ok, data = _request_json(
        "POST", f"{_api_url()}/v1/accounts/device/activate",
        {"account_token": token, "device_id": device_id(), "device_name": device_name()}, timeout=30,
    )
    if not ok:
        return False, str(data)
    payload = data if isinstance(data, dict) else {}
    activation_token = str(payload.get("activation_token", "")).strip()
    if not activation_token:
        return False, "O servidor não retornou uma ativação válida."
    write_license_state(
        {
            "status": "active",
            "role": str(payload.get("role", "PRO")).upper(),
            "plan": str(payload.get("plan", "LIFETIME")),
            "device_id": device_id(),
            "activated_at": _now_iso(),
            "last_checked_at": _now_iso(),
            "activation_token": activation_token,
            "source": "account",
            "server_url": _api_url(),
            "max_devices": payload.get("max_devices", 1),
            "active_devices": payload.get("active_devices", 1),
            "expires_at": payload.get("expires_at"),
            "account_email": str(acct.get("email", "")),
        }
    )
    acct["has_pro"] = True
    acct["role"] = str(payload.get("role", "PRO")).upper()
    acct["plan"] = str(payload.get("plan", "LIFETIME"))
    acct["active_devices"] = int(payload.get("active_devices") or 1)
    acct["max_devices"] = int(payload.get("max_devices") or 1)
    write_account_state(acct)
    return True, "Study Radar Pro ativado neste computador."


def fetch_account_license_key() -> tuple[bool, str]:
    token = str(read_account_state().get("account_token", "")).strip()
    if not token:
        return False, "Entre na sua conta primeiro."
    ok, data = _request_json("POST", f"{_api_url()}/v1/accounts/license-key", {"account_token": token}, timeout=20)
    if not ok:
        return False, str(data)
    key = normalize_key(str((data or {}).get("license_key", ""))) if isinstance(data, dict) else ""
    return (True, key) if key else (False, "O servidor não retornou a licença da sua conta.")


# ---------------------- Legacy/manual license support ----------------------
def activate_license(key: str) -> tuple[bool, str]:
    key = normalize_key(key)
    if not key:
        return False, "Digite uma chave de licença."
    if _key_hash(key) == OWNER_KEY_HASH:
        write_license_state(
            {"status": "active", "role": "OWNER", "plan": "LIFETIME", "device_id": device_id(),
             "activated_at": _now_iso(), "key_fingerprint": key[-9:], "source": "offline-owner"}
        )
        return True, "Licença OWNER ativada. Todos os recursos Pro foram liberados."
    ok, data = _request_json(
        "POST", f"{_api_url()}/v1/licenses/activate",
        {"license_key": key, "device_id": device_id(), "device_name": device_name()}, timeout=30,
    )
    if not ok:
        return False, str(data)
    payload = data if isinstance(data, dict) else {}
    token = str(payload.get("activation_token", "")).strip()
    if not token:
        return False, "O servidor não retornou um token de ativação válido."
    role = str(payload.get("role", "PRO")).upper()
    write_license_state(
        {"status": "active", "role": role if role in VALID_ROLES else "PRO", "plan": str(payload.get("plan", "LIFETIME")),
         "device_id": device_id(), "activated_at": _now_iso(), "last_checked_at": _now_iso(), "activation_token": token,
         "key_fingerprint": key[-9:], "source": "server", "server_url": _api_url(),
         "max_devices": payload.get("max_devices"), "active_devices": payload.get("active_devices"), "expires_at": payload.get("expires_at")}
    )
    return True, "Study Radar Pro ativado neste computador."


def verify_license() -> tuple[bool, str]:
    state = read_license_state()
    role = str(state.get("role", "FREE")).upper()
    if role == "OWNER" and license_status().active:
        return True, "Licença OWNER válida."
    api_url = str(state.get("server_url", "")).strip().rstrip("/") or _api_url()
    token = str(state.get("activation_token", "")).strip()
    if not api_url or not token:
        return False, "Não há token de ativação para verificar."
    ok, data = _request_json("POST", f"{api_url}/v1/licenses/verify", {"activation_token": token}, timeout=20)
    if not ok:
        return False, str(data)
    payload = data if isinstance(data, dict) else {}
    if not bool(payload.get("valid", False)):
        state["status"] = "inactive"; write_license_state(state)
        return False, "A licença não foi validada pelo servidor."
    role = str(payload.get("role", state.get("role", "PRO"))).upper()
    if role in VALID_ROLES:
        state["role"] = role
    state["plan"] = str(payload.get("plan", state.get("plan", "")))
    state["active_devices"] = payload.get("active_devices")
    state["max_devices"] = payload.get("max_devices")
    state["status"] = "active"; state["last_checked_at"] = _now_iso(); write_license_state(state)
    return True, "Licença verificada com sucesso."


def fetch_license_key() -> tuple[bool, str]:
    state = read_license_state()
    if str(state.get("role", "FREE")).upper() == "OWNER":
        return False, "A chave OWNER privada não é recuperada pelo servidor."
    if str(state.get("source", "")) == "account":
        return fetch_account_license_key()
    api_url = str(state.get("server_url", "")).strip().rstrip("/") or _api_url()
    token = str(state.get("activation_token", "")).strip()
    if not api_url or not token:
        return False, "Não há uma ativação comercial válida neste computador."
    ok, data = _request_json("POST", f"{api_url}/v1/licenses/key", {"activation_token": token}, timeout=20)
    if not ok:
        return False, str(data)
    key = normalize_key(str((data or {}).get("license_key", ""))) if isinstance(data, dict) else ""
    return (True, key) if key else (False, "O servidor não retornou a chave desta licença.")


def deactivate_license() -> tuple[bool, str]:
    state = read_license_state()
    if str(state.get("role", "")).upper() == "OWNER":
        clear_license_state()
        return True, "Licença OWNER removida deste Anki."
    api_url = str(state.get("server_url", "")).strip().rstrip("/") or _api_url()
    token = str(state.get("activation_token", "")).strip()
    if api_url and token:
        ok, message = _request_json("POST", f"{api_url}/v1/licenses/deactivate", {"activation_token": token}, timeout=20)
        if not ok:
            return False, f"O servidor não confirmou a desativação: {message}"
    clear_license_state()
    acct = read_account_state()
    if acct:
        acct["active_devices"] = 0
        write_account_state(acct)
    return True, "Dispositivo desativado. Sua conta Pro continua sendo sua."


# ----------------------------- Checkout ------------------------------------
def create_checkout(email: str | None = None) -> tuple[bool, Any]:
    acct = read_account_state()
    account_token = str(acct.get("account_token", "")).strip()
    if not account_token:
        return False, "Entre ou crie uma conta Study Radar antes de comprar o Pro."
    ok, data = _request_json(
        "POST", f"{_api_url()}/v1/checkout/create",
        {"email": (email or str(acct.get('email', ''))).strip() or None, "account_token": account_token}, timeout=75,
    )
    if not ok:
        return False, data
    payload = data if isinstance(data, dict) else {}
    if not payload.get("checkout_url") or not payload.get("session_token"):
        return False, "O servidor não retornou uma sessão de checkout válida."
    state = {
        "checkout_url": str(payload.get("checkout_url")), "session_token": str(payload.get("session_token")),
        "external_reference": str(payload.get("external_reference", "")), "expires_in_hours": int(payload.get("expires_in_hours", 24)),
        "created_at": _now_iso(), "status": "pending_payment", "account_email": str(acct.get("email", "")),
    }
    write_checkout_state(state)
    return True, state


def checkout_state() -> dict[str, Any]:
    return read_checkout_state()


def clear_pending_checkout() -> None:
    clear_checkout_state()


def check_checkout_status() -> tuple[bool, Any]:
    state = read_checkout_state()
    token = str(state.get("session_token", "")).strip()
    if not token:
        return False, "Não existe uma compra pendente neste Anki."
    query = urllib.parse.urlencode({"session_token": token})
    ok, data = _request_json("GET", f"{_api_url()}/v1/checkout/status?{query}", None, timeout=60)
    if not ok:
        return False, data
    payload = data if isinstance(data, dict) else {}
    state["status"] = str(payload.get("status", state.get("status", "pending_payment")))
    state["last_checked_at"] = _now_iso(); write_checkout_state(state)
    return True, payload


def activate_checkout_license(data: dict[str, Any]) -> tuple[bool, str]:
    """v1.3+: paid checkout is linked to the account, so activate the account's device."""
    if str(data.get("status", "")) != "approved":
        return False, "O pagamento ainda não foi aprovado."
    ok, message = refresh_account()
    if not ok:
        return False, f"Pagamento aprovado, mas não foi possível atualizar a conta: {message}"
    ok, message = activate_account_device()
    if ok:
        clear_checkout_state()
    return ok, message


# ----------------------------- HTTP helper ---------------------------------
def _request_json(method: str, url: str, payload: dict[str, Any] | None = None, *, timeout: int = 20) -> tuple[bool, Any]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json", "User-Agent": f"StudyRadar/{VERSION}"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return True, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        try:
            raw = exc.read().decode("utf-8")
            data = json.loads(raw) if raw else {}
            return False, data.get("detail") or data.get("message") or f"Erro HTTP {exc.code}"
        except Exception:
            return False, f"Erro HTTP {exc.code}"
    except urllib.error.URLError as exc:
        return False, f"Não foi possível conectar ao servidor: {getattr(exc, 'reason', exc)}"
    except Exception as exc:
        return False, f"Não foi possível acessar o servidor do Study Radar: {exc}"

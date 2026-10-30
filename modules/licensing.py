"""Commercial per-device activation using signed offline license tokens."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from license_core import get_device_id, verify_license

APP_ROOT = Path(__file__).resolve().parents[1]
LICENSE_FILE = APP_ROOT / "license.json"


def load_license() -> dict:
    try:
        value = json.loads(LICENSE_FILE.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_license(data: dict) -> None:
    temporary = LICENSE_FILE.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, LICENSE_FILE)


def is_activated() -> bool:
    data = load_license()
    return verify_license(str(data.get("token", "")), get_device_id()) is not None


def activate(token: str) -> bool:
    payload = verify_license(token, get_device_id())
    if payload is None:
        return False
    save_license(
        {
            "device_id": get_device_id(),
            "token": token.strip(),
            "issued_at": payload.get("issued_at"),
            "activated_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    return True


def current_status() -> str:
    return "Activated" if is_activated() else "Not activated"


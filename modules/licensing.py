"""Simple per-device activation helpers."""

import json
import os

from license_core import expected_key, get_device_id

LICENSE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "license.json")


def _normalize(key: str) -> str:
    return "".join(ch for ch in (key or "").upper() if ch.isalnum())


def load_license() -> dict:
    try:
        with open(LICENSE_FILE, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}


def save_license(data: dict) -> None:
    with open(LICENSE_FILE, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)


def is_activated() -> bool:
    data = load_license()
    if data.get("device_id") != get_device_id():
        return False
    return _normalize(data.get("key", "")) == _normalize(expected_key(get_device_id()))


def activate(key: str) -> bool:
    device_id = get_device_id()
    if _normalize(key) != _normalize(expected_key(device_id)):
        return False
    save_license({"device_id": device_id, "key": key.strip()})
    return True


def current_status() -> str:
    return "Activated" if is_activated() else "Not activated"

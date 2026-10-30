"""Issue exactly one stable key for each HBM-LIVECAM device id."""

from __future__ import annotations

import base64
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives.serialization import load_ssh_private_key

ROOT = Path(__file__).resolve().parent
PRIVATE_KEY_FILE = ROOT / "license-admin" / "hbm_license_ed25519"
REGISTRY_FILE = ROOT / "issued_licenses.json"
DEVICE_PATTERN = re.compile(r"^HBM-[0-9A-F]{16}$", re.IGNORECASE)


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def load_registry() -> list[dict]:
    try:
        value = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
        return value if isinstance(value, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def save_registry(records: list[dict]) -> None:
    temporary = REGISTRY_FILE.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, REGISTRY_FILE)


def issue(device_id: str) -> tuple[str, bool]:
    device_id = device_id.strip().upper()
    if not DEVICE_PATTERN.fullmatch(device_id):
        raise ValueError("Device ID khong hop le; dinh dang dung la HBM- + 16 ky tu hex.")

    records = load_registry()
    for record in records:
        if record.get("device_id") == device_id:
            return str(record.get("license_key") or record.get("key") or ""), False

    payload = {
        "product": "HBM-LIVECAM",
        "device_id": device_id,
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "license_type": "commercial-perpetual",
    }
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    private_key = load_ssh_private_key(PRIVATE_KEY_FILE.read_bytes(), password=None)
    token = f"HBM1.{_b64(payload_bytes)}.{_b64(private_key.sign(payload_bytes))}"
    records.append({**payload, "license_key": token, "status": "ISSUED"})
    save_registry(records)
    return token, True


def main(argv: list[str]) -> int:
    if len(argv) == 1:
        from license_core import get_device_id
        print(get_device_id())
        return 0
    if len(argv) != 2:
        print("Usage: python issue_license.py HBM-XXXXXXXXXXXXXXXX")
        return 1
    try:
        token, created = issue(argv[1])
    except ValueError as error:
        print(error)
        return 2
    print(token)
    print("SAVED" if created else "EXISTING")
    print(f"Registry: {REGISTRY_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

"""Core device identity + activation helpers (no heavy dependencies)."""

import hashlib
import hmac
import platform
import subprocess
import uuid

SECRET = b"HBM-LIVECAM-DEVICE-ACTIVATION-SECRET"


def _windows_uuid() -> str:
    try:
        output = subprocess.check_output(
            ["wmic", "csproduct", "get", "uuid"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        if len(lines) >= 2:
            return lines[1]
    except Exception:
        pass
    return ""


def get_device_id() -> str:
    parts = [
        platform.node(),
        platform.processor(),
        platform.machine(),
        str(uuid.getnode()),
        _windows_uuid(),
    ]
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return "HBM-" + digest[:16].upper()


def expected_key(device_id: str) -> str:
    digest = hmac.new(SECRET, device_id.encode("utf-8"), hashlib.sha256).hexdigest()
    raw = digest[:20].upper()
    return "-".join(raw[i:i + 5] for i in range(0, len(raw), 5))

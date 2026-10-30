"""Stable device identity and public-key license verification."""

from __future__ import annotations

import base64
import hashlib
import json
import platform
import subprocess
import uuid

from cryptography.hazmat.primitives.serialization import load_ssh_public_key

PRODUCT = "HBM-LIVECAM"
PUBLIC_KEY = b"ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHZpolEvjwQFa7O8Yez0jYZ995pMdmAZpmOkJ5kQJzU/"


def _windows_uuid() -> str:
    commands = [
        ["powershell.exe", "-NoProfile", "-Command", "(Get-CimInstance Win32_ComputerSystemProduct).UUID"],
        ["wmic", "csproduct", "get", "uuid"],
    ]
    for command in commands:
        try:
            output = subprocess.check_output(command, text=True, stderr=subprocess.DEVNULL)
            values = [line.strip() for line in output.splitlines() if line.strip() and "uuid" not in line.lower()]
            if values:
                return values[0]
        except Exception:
            continue
    return ""


def get_device_id() -> str:
    parts = [platform.node(), platform.machine(), str(uuid.getnode()), _windows_uuid()]
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return "HBM-" + digest[:16].upper()


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def verify_license(token: str, device_id: str | None = None) -> dict | None:
    try:
        prefix, encoded_payload, encoded_signature = token.strip().split(".")
        if prefix != "HBM1":
            return None
        payload_bytes = _b64decode(encoded_payload)
        signature = _b64decode(encoded_signature)
        load_ssh_public_key(PUBLIC_KEY).verify(signature, payload_bytes)
        payload = json.loads(payload_bytes.decode("utf-8"))
        expected_device = device_id or get_device_id()
        if payload.get("product") != PRODUCT or payload.get("device_id") != expected_device:
            return None
        return payload
    except Exception:
        return None


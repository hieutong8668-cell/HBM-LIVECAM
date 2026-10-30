"""Post-install hardware scan for HBM-LIVECAM.

Writes only non-secret device capability data into the installed application
directory. Camera enumeration is repeated by the UI on every application start.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _camera_devices() -> list[dict[str, object]]:
    devices: list[dict[str, object]] = []
    try:
        from cv2_enumerate_cameras import enumerate_cameras

        for camera in enumerate_cameras():
            devices.append(
                {
                    "index": int(camera.index),
                    "name": str(camera.name),
                    "path": str(getattr(camera, "path", "")),
                }
            )
    except Exception as error:
        devices.append({"scan_error": str(error)})
    return devices


def _nvidia() -> dict[str, object]:
    executable = shutil.which("nvidia-smi")
    if not executable:
        return {"available": False}
    try:
        result = subprocess.run(
            [
                executable,
                "--query-gpu=name,driver_version,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        )
        return {
            "available": True,
            "gpus": [line.strip() for line in result.stdout.splitlines() if line.strip()],
        }
    except Exception as error:
        return {"available": False, "scan_error": str(error)}


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "computer_name": os.environ.get("COMPUTERNAME", ""),
        "windows": platform.platform(),
        "python": sys.version.split()[0],
        "nvidia": _nvidia(),
        "cameras": _camera_devices(),
    }
    output = root / "device-scan.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[HBM-LIVECAM] Da quet {len(report['cameras'])} camera/thiet bi hinh anh.")
    print(f"[HBM-LIVECAM] Bao cao: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


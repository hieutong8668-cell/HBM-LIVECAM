import json
import os
import sys
from datetime import datetime

sys.path.insert(0, ".")
from license_core import expected_key, get_device_id

ISSUED_FILE = "issued_licenses.json"

def load_issued():
    try:
        with open(ISSUED_FILE, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return []

def save_issued(records):
    with open(ISSUED_FILE, "w", encoding="utf-8") as handle:
        json.dump(records, handle, indent=2)

if len(sys.argv) == 1:
    print(get_device_id())
    raise SystemExit(0)

if len(sys.argv) != 2:
    print("Usage: python issue_license.py [device_id]")
    raise SystemExit(1)

device_id = sys.argv[1]
key = expected_key(device_id)

records = load_issued()
records = [r for r in records if r.get("device_id") != device_id]
records.append({
    "device_id": device_id,
    "key": key,
    "issued_at": datetime.now().isoformat(timespec="seconds"),
})
save_issued(records)

print(key)

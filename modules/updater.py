"""Lightweight GitHub release checker for online updates."""

import json
import urllib.request

REPO = "hieutong8668-cell/HBM-LIVECAM"


def latest_release() -> dict:
    url = f"https://api.github.com/repos/{REPO}/releases/latest"
    request = urllib.request.Request(url, headers={"User-Agent": "HBM-LIVECAM"})
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


def check_for_updates(current_version: str) -> tuple[bool, str, str]:
    """Return (has_update, latest_tag, download_url)."""
    try:
        data = latest_release()
    except Exception:
        return False, "", ""
    tag = (data.get("tag_name") or "").lstrip("v")
    url = data.get("html_url") or ""
    return tag != current_version and bool(tag), tag, url

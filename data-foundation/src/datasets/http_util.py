"""Small HTTP helpers for dataset downloads.

Uses only the standard library. Browser-like headers are used so that open-access
hosts serve files; we never bypass authentication, paywalls, or access controls.
Some hosts (e.g. Dryad) sit behind an "Anubis" proof-of-work anti-bot challenge —
when detected we report ``blocked_by_antibot`` instead of attempting to defeat it.
"""
from __future__ import annotations

import shutil
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

_ANTIBOT_MARKERS = ("within.website", "anubis", "making sure you're not a bot", "validating...")


@dataclass
class FetchOutcome:
    ok: bool
    path: Path | None
    status: int
    bytes: int
    blocked_by_antibot: bool = False
    error: str = ""


def _is_antibot(payload_head: bytes, content_type: str) -> bool:
    if "text/html" not in content_type.lower():
        return False
    low = payload_head[:4096].lower()
    return any(marker.encode() in low for marker in _ANTIBOT_MARKERS)


def fetch(
    url: str,
    dest: Path,
    *,
    timeout: int = 60,
    max_bytes: int | None = None,
    referer: str | None = None,
) -> FetchOutcome:
    dest.parent.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": BROWSER_UA, "Accept": "*/*"}
    if referer:
        headers["Referer"] = referer
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get("Content-Type", "")
            head = response.read(4096)
            if _is_antibot(head, content_type):
                return FetchOutcome(False, None, response.status, 0, blocked_by_antibot=True,
                                    error="anti-bot challenge (Anubis) detected")
            total = 0
            with open(dest, "wb") as fh:
                fh.write(head)
                total = len(head)
                while True:
                    chunk = response.read(1 << 20)
                    if not chunk:
                        break
                    fh.write(chunk)
                    total += len(chunk)
                    if max_bytes is not None and total >= max_bytes:
                        break
            return FetchOutcome(True, dest, response.status, total)
    except urllib.error.HTTPError as exc:
        return FetchOutcome(False, None, exc.code, 0, error=f"HTTP {exc.code}")
    except Exception as exc:  # noqa: BLE001 - surface any network error as text
        return FetchOutcome(False, None, 0, 0, error=str(exc))


def find_in_downloads(filename: str) -> Path | None:
    downloads = Path.home() / "Downloads"
    candidate = downloads / filename
    if candidate.exists():
        return candidate
    for match in downloads.glob(f"*{filename}*"):
        return match
    return None


def adopt_local(source: Path, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != dest.resolve():
        shutil.copy2(source, dest)
    return dest

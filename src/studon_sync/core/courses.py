"""StudOn course URLs and titles."""

import re
import ssl
import urllib.request
from html import unescape
from pathlib import Path
from typing import Optional

import certifi

STUDON_URL = "https://www.studon.fau.de/studon"

_REF_PATTERNS = [
    r"[?&]ref_id=(\d+)",
    r"[?&]target=[a-z]+_(\d+)",
    r"goto[_a-z]*_[a-z]+_(\d+)\.html",
    r"/(?:crs|grp|fold|cat)_?(\d+)\.html",
    r"^\s*(\d+)\s*$",
]


def parse_ref_id(text: str) -> Optional[str]:
    """Extracts the ILIAS ref_id from a StudOn URL (or a bare number)."""
    for pattern in _REF_PATTERNS:
        if m := re.search(pattern, text, re.I):
            return m.group(1)
    return None


def course_url(ref_id: str) -> str:
    return f"{STUDON_URL}/ilias.php?baseClass=ilrepositorygui&ref_id={ref_id}"


def fetch_title(ref_id: str, timeout: float = 15) -> Optional[str]:
    """Reads the course title from the public StudOn page. None if it is not visible without login."""
    req = urllib.request.Request(course_url(ref_id), headers={"User-Agent": "studon-sync"})
    context = ssl.create_default_context(cafile=certifi.where())
    with urllib.request.urlopen(req, timeout=timeout, context=context) as resp:
        html = resp.read(200_000).decode("utf-8", "replace")
    m = re.search(r"<title>(.*?)</title>", html, re.S)
    if not m:
        return None
    title = unescape(m.group(1)).strip()
    title = re.sub(r"^(Info|Inhalt|Content):\s*", "", title)
    title = re.sub(r":\s*StudOn$", "", title).strip()
    return title if title and title.lower() != "studon" else None


def safe_folder_name(title: str) -> str:
    name = re.sub(r'[/\\:*?"<>|]+', "-", title).strip(" .")
    return name or "StudOn-Kurs"


def default_target(title: str, base_dir: str, taken: set[str]) -> str:
    """base_dir/<title>; if that folder already exists or is used by another course, base_dir/StudOn-<title>."""
    base = Path(base_dir).expanduser()
    name = safe_folder_name(title)
    candidate = base / name
    if candidate.exists() or str(candidate) in taken:
        candidate = base / f"StudOn-{name}"
    return str(candidate)

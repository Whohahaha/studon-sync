"""Keeps the log folder small: normal runs are dropped, failures are kept for a while.

Policy (run after every sync):
- the newest KEEP_RECENT logs are always kept, whatever their result;
- older logs of successful syncs and of listing runs are deleted;
- older logs of failed or unfinished syncs are kept for KEEP_FAILED_DAYS;
- login-debug pages are kept for KEEP_DEBUG_DAYS.
"""

import time
from pathlib import Path
from typing import Optional

from ..i18n import STRINGS
from . import paths

KEEP_RECENT = 5
KEEP_FAILED_DAYS = 60
KEEP_DEBUG_DAYS = 30

# "结果：成功（日志：" etc. in every language, so a later language switch does not matter.
_OK_PREFIXES = tuple(lang["sum.ok"].split("{")[0] for lang in STRINGS.values() if "sum.ok" in lang)


def _succeeded(log: Path) -> bool:
    try:
        lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return False
    return any(line.startswith(_OK_PREFIXES) for line in lines[-3:])


def clean_logs(log_dir: Optional[Path] = None, now: Optional[float] = None) -> list[Path]:
    """Deletes logs the policy does not keep. Returns the deleted paths."""
    log_dir = log_dir or paths.log_dir()
    now = now if now is not None else time.time()
    deleted: list[Path] = []

    def age_days(p: Path) -> float:
        return (now - p.stat().st_mtime) / 86400

    def delete(p: Path) -> None:
        try:
            p.unlink()
            deleted.append(p)
        except OSError:
            pass

    # File names carry the start time, so name order == time order within each kind.
    runs = [*log_dir.glob("sync-*.log"), *log_dir.glob("list-*.log")]
    runs.sort(key=lambda p: p.name.split("-", 1)[1])
    for log in runs[:-KEEP_RECENT] if len(runs) > KEEP_RECENT else []:
        if log.name.startswith("list-") or _succeeded(log):
            delete(log)
        elif age_days(log) > KEEP_FAILED_DAYS:
            delete(log)

    for page in log_dir.glob("login-debug-*.html"):
        if age_days(page) > KEEP_DEBUG_DAYS:
            delete(page)
    return deleted

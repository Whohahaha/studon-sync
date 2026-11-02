"""OS integration: background scheduler (runs `studon-sync scheduled` every 15 min) and notifications."""

import plistlib
import subprocess
import sys
from pathlib import Path

LABEL = "de.fau.studon-sync"
TASK_NAME = "StudOnSync"


def _command(*args: str) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, *args]
    return [sys.executable, "-m", "studon_sync", *args]


def _plist() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def scheduler_installed() -> bool:
    if sys.platform == "darwin":
        return _plist().exists()
    if sys.platform == "win32":
        return subprocess.run(["schtasks", "/Query", "/TN", TASK_NAME], capture_output=True).returncode == 0
    return False


def install_scheduler() -> None:
    """Checks every 15 minutes (and at login) whether a sync is due; settings decide the actual times."""
    if sys.platform == "darwin":
        from .core import paths

        log = str(paths.log_dir() / "scheduler.log")
        plist = {
            "Label": LABEL,
            "ProgramArguments": _command("scheduled"),
            "StartInterval": 900,
            "RunAtLoad": True,
            "ProcessType": "Background",
            "StandardOutPath": log,
            "StandardErrorPath": log,
        }
        uninstall_scheduler()
        _plist().parent.mkdir(parents=True, exist_ok=True)
        _plist().write_bytes(plistlib.dumps(plist))
        subprocess.run(["launchctl", "bootstrap", f"gui/{_uid()}", str(_plist())], check=False, capture_output=True)
    elif sys.platform == "win32":
        cmd = " ".join(f'"{a}"' for a in _command("scheduled"))
        subprocess.run(
            ["schtasks", "/Create", "/F", "/SC", "MINUTE", "/MO", "15", "/TN", TASK_NAME, "/TR", cmd],
            check=True,
            capture_output=True,
        )
    else:
        raise NotImplementedError("automatic sync is not supported on this platform yet; use cron with `studon-sync scheduled`")


def uninstall_scheduler() -> None:
    if sys.platform == "darwin":
        subprocess.run(["launchctl", "bootout", f"gui/{_uid()}/{LABEL}"], check=False, capture_output=True)
        _plist().unlink(missing_ok=True)
    elif sys.platform == "win32":
        subprocess.run(["schtasks", "/Delete", "/F", "/TN", TASK_NAME], check=False, capture_output=True)


def _uid() -> int:
    import os

    return os.getuid()


def notify(title: str, text: str) -> None:
    if sys.platform == "darwin":
        script = f"display notification {_applescript_str(text)} with title {_applescript_str(title)}"
        subprocess.run(["osascript", "-e", script], check=False, capture_output=True)


def _applescript_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def open_path(path: Path) -> None:
    if sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    elif sys.platform == "win32":
        import os

        os.startfile(str(path))  # type: ignore[attr-defined]
    else:
        subprocess.run(["xdg-open", str(path)], check=False)

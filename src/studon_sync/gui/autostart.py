"""'Start at login' for macOS (LaunchAgent), Windows (Run key) and Linux (XDG autostart)."""

import os
import plistlib
import sys
from pathlib import Path

LABEL = "de.fau.studon-sync"


def _command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "gui", "--background"]
    return [sys.executable, "-m", "studon_sync", "gui", "--background"]


def _mac_plist() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def _linux_desktop() -> Path:
    return Path.home() / ".config" / "autostart" / "studon-sync.desktop"


def set_enabled(enabled: bool) -> None:
    if sys.platform == "darwin":
        path = _mac_plist()
        if enabled:
            path.parent.mkdir(parents=True, exist_ok=True)
            env = {"PYTHONPATH": os.environ["PYTHONPATH"]} if "PYTHONPATH" in os.environ else {}
            plist = {"Label": LABEL, "ProgramArguments": _command(), "RunAtLoad": True, "ProcessType": "Interactive"}
            if env:
                plist["EnvironmentVariables"] = env
            path.write_bytes(plistlib.dumps(plist))
        else:
            path.unlink(missing_ok=True)
    elif sys.platform == "win32":
        import winreg

        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
        with key:
            if enabled:
                winreg.SetValueEx(key, "StudOnSync", 0, winreg.REG_SZ, " ".join(f'"{a}"' for a in _command()))
            else:
                try:
                    winreg.DeleteValue(key, "StudOnSync")
                except FileNotFoundError:
                    pass
    else:
        path = _linux_desktop()
        if enabled:
            path.parent.mkdir(parents=True, exist_ok=True)
            cmd = " ".join(f'"{a}"' for a in _command())
            path.write_text(f"[Desktop Entry]\nType=Application\nName=StudOn Sync\nExec={cmd}\n", encoding="utf-8")
        else:
            path.unlink(missing_ok=True)

"""Per-user locations (outside the repo/app folder)."""

from pathlib import Path

from platformdirs import user_config_path, user_log_path

APP_NAME = "StudOn Sync"


def config_dir() -> Path:
    path = user_config_path(APP_NAME, appauthor=False)
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_dir() -> Path:
    path = user_log_path(APP_NAME, appauthor=False)
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_file() -> Path:
    return config_dir() / "settings.json"


def pferd_config_file() -> Path:
    return config_dir() / "pferd.cfg"


def lock_file() -> Path:
    return config_dir() / "sync.lock"

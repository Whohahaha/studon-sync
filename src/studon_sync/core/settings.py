"""User settings, stored as JSON in the per-user config dir."""

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from . import paths


@dataclass
class Course:
    ref_id: str
    title: str
    target_dir: str
    enabled: bool = True
    # explicit choices from the file selection page: {"path/or/folder": True|False}
    selection: dict[str, bool] = field(default_factory=dict)
    new_files: str = "auto"  # "auto": download new files right away; "review": wait until selected

    @property
    def url(self) -> str:
        from .courses import course_url

        return course_url(self.ref_id)


@dataclass
class Schedule:
    mode: str = "off"  # "off" | "daily" | "interval"
    time: str = "08:00"  # for "daily", HH:MM local time
    hours: int = 6  # for "interval"


@dataclass
class Settings:
    language: str = "zh"
    default_target_dir: str = str(Path.home() / "Documents" / "StudOn")
    courses: list[Course] = field(default_factory=list)
    schedule: Schedule = field(default_factory=Schedule)
    last_sync: Optional[str] = None  # ISO timestamp of the last finished sync
    last_sync_ok: Optional[bool] = None

    def course(self, ref_id: str) -> Optional[Course]:
        return next((c for c in self.courses if c.ref_id == ref_id), None)


def load() -> Settings:
    path = paths.settings_file()
    if not path.exists():
        return Settings()
    data = json.loads(path.read_text(encoding="utf-8"))
    courses = [Course(**c) for c in data.pop("courses", [])]
    schedule = Schedule(**data.pop("schedule", {}))
    known = Settings.__dataclass_fields__.keys()
    return Settings(courses=courses, schedule=schedule, **{k: v for k, v in data.items() if k in known})


def save(settings: Settings) -> None:
    path = paths.settings_file()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)

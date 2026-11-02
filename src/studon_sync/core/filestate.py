"""
Per-course file state, file selection and protection of locally edited files.

Every course folder gets a hidden `.studon-sync/` directory:
  state.json   what we downloaded (remote date + SHA-256 as downloaded) and what StudOn lists
  versions/    old copies of files that were replaced by a newer StudOn version
  run.jsonl    decisions of the running sync (merged into state.json afterwards)

Rules (see decide()):
  - new remote file, nothing local            -> download
  - local file exists but we have no record   -> adopt it as-is (no download); since we never
                                                 saw it untouched, a newer version is saved next to it
  - we downloaded it but the user deleted it  -> leave it deleted (until re-selected)
  - remote unchanged                          -> nothing
  - remote newer, local untouched (same hash) -> move old copy to versions/, download new
  - remote newer, local edited (hash differs) -> keep the user's file, save the new one
                                                 next to it as "<name> (StudOn YYYY-MM-DD).<ext>"
  - file disappeared from StudOn              -> never deleted locally, only marked
"""

import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any, Optional

STATE_DIR = ".studon-sync"
HIDDEN_NAMES = {STATE_DIR, ".cookies", ".report", ".DS_Store"}
DEFAULT_EXCLUDED_NAMES = {"Description.html"}  # ILIAS info texts PFERD renders; change on every visit


class Action(Enum):
    SKIP_UNSELECTED = "skip_unselected"
    SKIP_DELETED = "skip_deleted"
    SKIP_UNCHANGED = "skip_unchanged"
    ADOPT = "adopt"
    DOWNLOAD_NEW = "download_new"
    REPLACE = "replace"
    SAVE_ALT = "save_alt"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _newer(remote: Optional[str], known: Optional[str]) -> bool:
    if remote is None or known is None:
        return False  # without a remote date we cannot tell; never risk an overwrite
    return datetime.fromisoformat(remote) > datetime.fromisoformat(known)


def is_selected(path: str, selection: dict[str, bool], new_files: str, known: bool) -> bool:
    """Explicit decision on the path or its nearest ancestor folder wins; otherwise the defaults."""
    p = PurePosixPath(path)
    for candidate in [p, *p.parents]:
        key = str(candidate)
        if key in selection:
            return selection[key]
    if p.name in DEFAULT_EXCLUDED_NAMES:
        return False
    return new_files == "auto" or known


def has_decision(path: str, selection: dict[str, bool]) -> bool:
    p = PurePosixPath(path)
    return any(str(c) in selection for c in [p, *p.parents])


def decide(entry: Optional[dict], remote_mtime: Optional[str], local: Path, selected: bool) -> Action:
    if not selected:
        return Action.SKIP_UNSELECTED
    if entry is None:
        return Action.ADOPT if local.exists() else Action.DOWNLOAD_NEW
    if not local.exists():
        return Action.SKIP_DELETED
    if not _newer(remote_mtime, entry.get("remote_mtime")):
        return Action.SKIP_UNCHANGED
    if not entry.get("adopted") and sha256_file(local) == entry.get("sha256"):
        return Action.REPLACE
    return Action.SAVE_ALT


def alt_path(path: str, remote_mtime: Optional[str], root: Path) -> str:
    """'a/b.pdf' -> 'a/b (StudOn 2026-11-02).pdf', with ' 2', ' 3', ... if that exists too."""
    p = PurePosixPath(path)
    date = (datetime.fromisoformat(remote_mtime) if remote_mtime else datetime.now()).strftime("%Y-%m-%d")
    n = 1
    while True:
        suffix = f" (StudOn {date})" if n == 1 else f" (StudOn {date} {n})"
        candidate = str(p.with_name(f"{p.stem}{suffix}{p.suffix}"))
        if not (root / candidate).exists():
            return candidate
        n += 1


DOWNLOADING = (Action.DOWNLOAD_NEW, Action.REPLACE, Action.SAVE_ALT)


def plan(
    state: "CourseState", rel: str, remote_mtime: Optional[str], selection: dict[str, bool], new_files: str
) -> tuple[Action, str]:
    """Decides what to do with one remote file, prepares it (backup) and journals it.

    Returns the action and the path (relative to the course root) to download to, if any."""
    entry = state.files.get(rel)
    selected = is_selected(rel, selection, new_files, known=entry is not None)
    action = decide(entry, remote_mtime, state.root / rel, selected)
    event: dict[str, Any] = {"path": rel, "action": action.value, "remote_mtime": remote_mtime}
    target = rel
    if action == Action.SKIP_UNSELECTED:
        event["pending"] = new_files == "review" and not has_decision(rel, selection)
    elif action == Action.REPLACE:
        event["backup"] = state.backup(rel)
    elif action == Action.SAVE_ALT:
        target = event["alt"] = alt_path(rel, remote_mtime, state.root)
    state.log(**event)
    return action, target


class CourseState:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.dir = root / STATE_DIR
        self.file = self.dir / "state.json"
        self.data: dict[str, Any] = {"files": {}, "remote": {}, "last_run": {}}
        if self.file.exists():
            self.data.update(json.loads(self.file.read_text(encoding="utf-8")))

    @property
    def files(self) -> dict[str, dict]:
        return self.data["files"]

    @property
    def remote(self) -> dict[str, dict]:
        return self.data["remote"]

    def save(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.file)

    # ---- during the PFERD run (subprocess) -------------------------------------------------

    def journal_path(self) -> Path:
        return self.dir / "run.jsonl"

    def start_journal(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        self.journal_path().write_text("", encoding="utf-8")

    def log(self, **event: Any) -> None:
        with self.journal_path().open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def backup(self, path: str) -> str:
        """Moves the current local copy into versions/ and returns its path there (relative to root)."""
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        rel = PurePosixPath(STATE_DIR, "versions", stamp, path)
        dest = self.root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(self.root / path), dest)
        return str(rel)

    # ---- after the run (parent process) ----------------------------------------------------

    def apply_journal(self, crawl_ok: bool, started: datetime) -> "RunSummary":
        summary = RunSummary()
        if not self.journal_path().exists():
            return summary
        now = datetime.now().isoformat(timespec="seconds")
        seen: set[str] = set()
        for line in self.journal_path().read_text(encoding="utf-8").splitlines():
            ev = json.loads(line)
            path, action = ev["path"], ev["action"]
            seen.add(path)
            rec = self.remote.setdefault(path, {"first_seen": now})
            rec.update(mtime=ev.get("remote_mtime"), last_seen=now)
            rec.pop("removed", None)
            if action == Action.SKIP_UNSELECTED.value and ev.get("pending"):
                summary.pending.append(path)
            elif action == Action.ADOPT.value:
                local = self.root / path
                remote = ev.get("remote_mtime")
                # PFERD stamps downloads with the remote date; a file still carrying it is untouched.
                untouched = remote is not None and abs(local.stat().st_mtime - datetime.fromisoformat(remote).timestamp()) < 2
                self.files[path] = {"remote_mtime": remote, "sha256": sha256_file(local)}
                if not untouched:
                    self.files[path]["adopted"] = True
            elif action in (Action.DOWNLOAD_NEW.value, Action.REPLACE.value):
                local = self.root / path
                if local.exists():
                    self.files[path] = {"remote_mtime": ev.get("remote_mtime"), "sha256": sha256_file(local)}
                    (summary.added if action == Action.DOWNLOAD_NEW.value else summary.updated).append(path)
                elif ev.get("backup"):  # download failed: put the previous copy back
                    shutil.move(str(self.root / ev["backup"]), local)
            elif action == Action.SAVE_ALT.value:
                if (self.root / ev["alt"]).exists():
                    entry = self.files[path]
                    entry["remote_mtime"] = ev.get("remote_mtime")  # user's file keeps its old hash on purpose
                    entry.setdefault("alt_versions", []).append(ev["alt"])
                    summary.kept_edited.append((path, ev["alt"]))
            elif action == Action.SKIP_DELETED.value:
                summary.deleted_locally.append(path)
        if crawl_ok:
            for path, rec in self.remote.items():
                if path not in seen and not rec.get("removed"):
                    rec["removed"] = now
                    summary.removed_remote.append(path)
        self.data["last_run"] = {"at": now, "ok": crawl_ok}
        self.journal_path().unlink()
        self.save()
        return summary

    def forget(self, path: str) -> None:
        """'Download again': drop our record so a deleted file is fetched on the next sync."""
        for key in [k for k in self.files if k == path or k.startswith(path.rstrip("/") + "/")]:
            del self.files[key]
        self.save()


@dataclass
class RunSummary:
    added: list[str]
    updated: list[str]
    kept_edited: list[tuple[str, str]]  # (user's file, new StudOn version saved next to it)
    pending: list[str]
    deleted_locally: list[str]
    removed_remote: list[str]

    def __init__(self) -> None:
        self.added, self.updated, self.kept_edited = [], [], []
        self.pending, self.deleted_locally, self.removed_remote = [], [], []

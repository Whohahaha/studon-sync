"""Python side of the web UI: every public method is callable from JS as window.pywebview.api.<name>()."""

import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from .. import system
from ..core import courses, credentials, paths, runner
from ..core import settings as settings_mod
from ..core.filestate import CourseState, has_decision, is_selected, sha256_file
from ..core.fau_login import LoginError
from ..core.settings import Course
from .. import i18n
from ..i18n import t


class Api:
    def __init__(self) -> None:
        self._window: Any = None
        self._lines: list[str] = []
        self._job: Optional[str] = None  # "sync" | "list"
        self._result: Optional[dict] = None
        self._lock = threading.Lock()

    def attach(self, window: Any) -> None:
        self._window = window

    # ---- general -------------------------------------------------------------------------

    def strings(self) -> dict[str, str]:
        return i18n.strings()

    def language(self) -> dict:
        return {
            "setting": settings_mod.load().language,
            "current": i18n.current(),
            "options": i18n.LANGUAGES,
        }

    def set_language(self, setting: str) -> dict[str, str]:
        """Saves the language setting ("auto" or a code), switches to it and returns the new strings."""
        if setting != "auto" and setting not in i18n.STRINGS:
            setting = "auto"
        s = settings_mod.load()
        s.language = setting
        settings_mod.save(s)
        i18n.set_language(setting)
        if self._window is not None:
            self._window.set_title(t("app.title"))
        return i18n.strings()

    def state(self) -> dict:
        s = settings_mod.load()
        return {
            "username": credentials.stored_username(),
            "has_password": credentials.has_password(),
            "has_secret": credentials.has_totp_secret(),
            "default_target_dir": s.default_target_dir,
            "courses": [self._course_info(c) for c in s.courses],
            "schedule": {"mode": s.schedule.mode, "time": s.schedule.time, "hours": s.schedule.hours},
            "scheduler_installed": system.scheduler_installed(),
            "last_sync": s.last_sync,
            "last_sync_ok": s.last_sync_ok,
            "job": self._job,
        }

    def _course_info(self, c: Course) -> dict:
        state = CourseState(Path(c.target_dir).expanduser())
        pending = sum(
            1
            for p in state.remote
            if not state.remote[p].get("removed")
            and c.new_files == "review"
            and not has_decision(p, c.selection)
            and not is_selected(p, c.selection, c.new_files, known=p in state.files)
        )
        return {
            "ref_id": c.ref_id,
            "title": c.title,
            "target_dir": c.target_dir,
            "enabled": c.enabled,
            "new_files": c.new_files,
            "files": len(state.files),
            "pending": pending,
            "url": c.url,
        }

    # ---- account -------------------------------------------------------------------------

    def save_credentials(self, username: str, password: str, secret: str) -> dict:
        try:
            credentials.save(username or None, password or None, secret or None)
        except ValueError:
            return {"ok": False, "error": t("acc.bad_secret")}
        return {"ok": True}

    def totp(self, secret: str = "") -> dict:
        try:
            code, left = credentials.current_code(secret or None)
        except ValueError:
            return {"code": None, "error": t("acc.bad_secret") if secret else None}
        return {"code": code, "left": left}

    def test_login(self) -> dict:
        try:
            ok = runner.test_login()
        except LoginError as e:
            return {"ok": False, "error": str(e)}
        except Exception as e:  # network errors etc.
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}
        return {"ok": ok, "error": None if ok else "StudOn"}

    # ---- courses -------------------------------------------------------------------------

    def add_course(self, url: str) -> dict:
        ref_id = courses.parse_ref_id(url)
        if not ref_id:
            return {"ok": False, "error": t("crs.bad_url")}
        s = settings_mod.load()
        if s.course(ref_id):
            return {"ok": False, "error": t("crs.exists")}
        try:
            title = courses.fetch_title(ref_id) or f"StudOn-{ref_id}"
        except OSError:
            title = f"StudOn-{ref_id}"
        target = courses.default_target(title, s.default_target_dir, {c.target_dir for c in s.courses})
        s.courses.append(Course(ref_id=ref_id, title=title, target_dir=target))
        settings_mod.save(s)
        return {"ok": True, "ref_id": ref_id}

    def update_course(self, ref_id: str, patch: dict) -> dict:
        s = settings_mod.load()
        c = s.course(ref_id)
        if c is None:
            return {"ok": False}
        for key in ("enabled", "new_files", "title", "target_dir"):
            if key in patch:
                setattr(c, key, patch[key])
        settings_mod.save(s)
        return {"ok": True}

    def remove_course(self, ref_id: str) -> dict:
        s = settings_mod.load()
        s.courses = [c for c in s.courses if c.ref_id != ref_id]  # downloaded files stay where they are
        settings_mod.save(s)
        return {"ok": True}

    def choose_folder(self, ref_id: str = "") -> Optional[str]:
        import webview

        s = settings_mod.load()
        c = s.course(ref_id) if ref_id else None
        start = str(Path(c.target_dir if c else s.default_target_dir).expanduser())
        chosen = self._window.create_file_dialog(webview.FileDialog.FOLDER, directory=start)
        if not chosen:
            return None
        folder = chosen[0] if isinstance(chosen, (list, tuple)) else chosen
        if c:
            c.target_dir = folder
        else:
            s.default_target_dir = folder
        settings_mod.save(s)
        return folder

    def open_folder(self, ref_id: str = "") -> None:
        if ref_id and (c := settings_mod.load().course(ref_id)):
            path = Path(c.target_dir).expanduser()
            path.mkdir(parents=True, exist_ok=True)
        else:
            path = paths.log_dir()
        system.open_path(path)

    def open_file(self, ref_id: str, rel: str) -> None:
        if c := settings_mod.load().course(ref_id):
            path = Path(c.target_dir).expanduser() / rel
            system.open_path(path if path.exists() else path.parent)

    # ---- file selection ------------------------------------------------------------------

    def tree(self, ref_id: str) -> dict:
        c = settings_mod.load().course(ref_id)
        if c is None:
            return {"files": []}
        root = Path(c.target_dir).expanduser()
        state = CourseState(root)
        recent = datetime.now() - timedelta(days=7)
        since = state.data.get("catalog_since")
        files = []
        for rel, rec in sorted(state.remote.items()):
            entry = state.files.get(rel)
            local = root / rel
            selected = is_selected(rel, c.selection, c.new_files, known=entry is not None)
            if rec.get("removed"):
                status = "removed_remote"
            elif entry and not local.exists():
                status = "deleted_locally"
            elif entry and entry.get("alt_versions"):
                status = "kept_edited"
            elif entry:
                status = "edited" if _edited(local, entry) else "downloaded"
            elif not selected and c.new_files == "review" and not has_decision(rel, c.selection):
                status = "pending"
            elif not selected:
                status = "unselected"
            else:
                status = "not_yet"
            first_seen = rec.get("first_seen")
            files.append(
                {
                    "path": rel,
                    "mtime": rec.get("mtime"),
                    "status": status,
                    "selected": selected,
                    "new": bool(first_seen and since)
                    and first_seen > since
                    and datetime.fromisoformat(first_seen) > recent,
                    "alt_versions": (entry or {}).get("alt_versions", []),
                }
            )
        return {"files": files, "last_run": state.data.get("last_run", {}), "selection": c.selection}

    def set_selection(self, ref_id: str, rel: str, value: bool) -> dict:
        s = settings_mod.load()
        c = s.course(ref_id)
        if c is None:
            return {"ok": False}
        prefix = rel.rstrip("/") + "/"
        c.selection = {k: v for k, v in c.selection.items() if k != rel and not k.startswith(prefix)}
        c.selection[rel] = value
        settings_mod.save(s)
        if value:  # re-checking a file the user deleted means "download it again"
            state = CourseState(Path(c.target_dir).expanduser())
            root = state.root
            gone = [p for p in state.files if (p == rel or p.startswith(prefix)) and not (root / p).exists()]
            for p in gone:
                state.forget(p)
        return {"ok": True}

    # ---- sync / listing jobs -------------------------------------------------------------

    def start_sync(self, ref_ids: Optional[list[str]] = None) -> dict:
        return self._start("sync", ref_ids)

    def refresh_tree(self, ref_id: str) -> dict:
        return self._start("list", [ref_id])

    def _start(self, job: str, ref_ids: Optional[list[str]]) -> dict:
        with self._lock:
            if self._job or runner.is_running():
                return {"ok": False, "error": t("err.busy")}
            self._job, self._lines, self._result = job, [], None

        def work() -> None:
            try:
                result = runner.run_sync(self._lines.append, ref_ids=ref_ids, list_only=job == "list")
                self._result = {
                    "ok": result.ok,
                    "error": result.error,
                    "added": result.added,
                    "changed": result.changed,
                    "kept_edited": result.kept_edited,
                    "log": str(result.log_path),
                }
                if job == "sync" and (not result.ok or result.added or result.changed):
                    system.notify(t("app.title"), _notification(self._result))
            except Exception as e:
                self._result = {"ok": False, "error": f"{type(e).__name__}: {e}"}
            finally:
                self._job = None

        threading.Thread(target=work, daemon=True).start()
        return {"ok": True}

    def progress(self, since: int = 0) -> dict:
        return {"job": self._job, "lines": self._lines[since:], "next": len(self._lines), "result": self._result}

    # ---- schedule ------------------------------------------------------------------------

    def set_schedule(self, mode: str, time: str, hours: int) -> dict:
        s = settings_mod.load()
        s.schedule.mode, s.schedule.time, s.schedule.hours = mode, time, int(hours)
        settings_mod.save(s)
        try:
            if mode == "off":
                system.uninstall_scheduler()
            else:
                system.install_scheduler()
        except Exception as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True}


def _edited(local: Path, entry: dict) -> bool:
    if not local.exists():
        return False
    remote = entry.get("remote_mtime")
    if remote and abs(local.stat().st_mtime - datetime.fromisoformat(remote).timestamp()) < 2:
        return False  # still carries the StudOn date: untouched, no need to hash
    return sha256_file(local) != entry.get("sha256")


def _notification(result: dict) -> str:
    if not result["ok"]:
        return t("notify.failed")
    text = t("notify.new", added=result["added"], changed=result["changed"])
    if result["kept_edited"]:
        text += " · " + t("notify.kept_edited", n=result["kept_edited"])
    return text

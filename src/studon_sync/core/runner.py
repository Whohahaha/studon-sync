"""Runs PFERD for all enabled courses and summarizes what changed."""

import asyncio
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from ..i18n import t
from . import paths
from . import settings as settings_mod
from .courses import STUDON_URL
from .settings import Course, Settings

# Only files: containers (folders, sessions, the course info tab) are entered to find them.
ALLOWED_TYPES = {"file", "folder", "meeting", "info_tab"}


@dataclass
class CourseResult:
    course: Course
    added: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class SyncResult:
    ok: bool
    log_path: Path
    courses: list[CourseResult] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def added(self) -> int:
        return sum(len(c.added) for c in self.courses)

    @property
    def changed(self) -> int:
        return sum(len(c.changed) for c in self.courses)


def _section(course: Course) -> str:
    return f"crawl:studon-{course.ref_id}"


def build_pferd_config(courses: list[Course]) -> str:
    lines = [
        "[DEFAULT]",
        f"working_dir = {Path.home()}",
        "share_cookies = true",
        "",
        "[auth:studon]",
        "# placeholder: the real login (fau_login.py) reads the OS keyring",
        "type = simple",
        "username = studon-sync",
    ]
    for course in courses:
        lines += [
            "",
            f"[{_section(course)}]",
            "type = ilias-web",
            f"base_url = {STUDON_URL}",
            "login_type = shibboleth",
            "auth = auth:studon",
            f"target = {course.ref_id}",
            f"output_dir = {Path(course.target_dir).expanduser()}",
            "redownload = never-smart",
            "on_conflict = no-delete",
            "tasks = 1",
            "downloads = 1",
            "task_delay = 1",
            "videos = no",
            "forums = no",
            "links = ignore",
        ]
    return "\n".join(lines) + "\n"


def _pferd_command(config: Path) -> list[str]:
    if getattr(sys, "frozen", False):  # PyInstaller app: the executable dispatches "_pferd" itself
        return [sys.executable, "_pferd", str(config)]
    return [sys.executable, "-m", "studon_sync", "_pferd", str(config)]


class _Lock:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._fd: Optional[int] = None

    def acquire(self) -> bool:
        self._fd = os.open(self._path, os.O_RDWR | os.O_CREAT)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self._fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(self._fd)
            self._fd = None
            return False
        return True

    def release(self) -> None:
        if self._fd is not None:
            os.close(self._fd)  # closing releases the lock
            self._fd = None


def is_running() -> bool:
    lock = _Lock(paths.lock_file())
    if lock.acquire():
        lock.release()
        return False
    return True


def run_sync(on_line: Callable[[str], None] = lambda line: None) -> SyncResult:
    """Syncs all enabled courses. `on_line` receives every output line (also written to the log)."""
    settings = settings_mod.load()
    started = datetime.now()
    log_path = paths.log_dir() / f"sync-{started:%Y%m%d-%H%M%S}.log"
    courses = [c for c in settings.courses if c.enabled]

    lock = _Lock(paths.lock_file())
    if not lock.acquire():
        return SyncResult(False, log_path, error=t("err.busy"))
    try:
        with log_path.open("w", encoding="utf-8") as log:

            def out(line: str) -> None:
                log.write(line + "\n")
                log.flush()
                on_line(line)

            out(f"=== StudOn sync {started:%Y-%m-%d %H:%M:%S} ===")
            if not courses:
                out(t("err.no_courses"))
                return SyncResult(False, log_path, error=t("err.no_courses"))

            config = paths.pferd_config_file()
            config.write_text(build_pferd_config(courses), encoding="utf-8")
            for course in courses:
                Path(course.target_dir).expanduser().mkdir(parents=True, exist_ok=True)

            proc = subprocess.Popen(
                _pferd_command(config),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env={**os.environ, "COLUMNS": "200", "PYTHONIOENCODING": "utf-8"},
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                out(line.rstrip("\n"))
            code = proc.wait()

            result = SyncResult(code == 0, log_path)
            for course in courses:
                cr = CourseResult(course)
                report = Path(course.target_dir).expanduser() / ".report"
                if report.exists() and report.stat().st_mtime >= started.timestamp():
                    data = json.loads(report.read_text(encoding="utf-8"))
                    cr.added, cr.changed = data.get("added", []), data.get("changed", [])
                    cr.errors = data.get("encountered_errors", [])
                else:
                    cr.errors = ["no report written"]
                result.ok = result.ok and not cr.errors
                result.courses.append(cr)

            out("")
            out(t("sum.header"))
            for cr in result.courses:
                out(t("sum.course", title=cr.course.title, target=cr.course.target_dir))
                out(t("sum.counts", added=len(cr.added), changed=len(cr.changed)))
                out_lines = [f"    + {p}" for p in cr.added] + [f"    ~ {p}" for p in cr.changed]
                for line in out_lines:
                    out(line)
                if cr.errors:
                    out(t("sum.errors", n=len(cr.errors)))
                    for e in cr.errors:
                        out(f"    ! {e}")
            out(t("sum.ok" if result.ok else "sum.failed", log=log_path))
    finally:
        lock.release()

    settings = settings_mod.load()  # reload: the GUI may have changed settings meanwhile
    settings.last_sync = datetime.now().isoformat(timespec="seconds")
    settings.last_sync_ok = result.ok
    settings_mod.save(settings)
    return result


def test_login() -> bool:
    """Logs in once and checks that StudOn considers us logged in. Raises LoginError."""

    async def run() -> bool:
        import ssl

        import aiohttp
        import certifi
        from PFERD.crawl.ilias.kit_ilias_html import IliasPage, IliasSoup
        from PFERD.utils import soupify

        from . import fau_login

        connector = aiohttp.TCPConnector(ssl=ssl.create_default_context(cafile=certifi.where()))
        async with aiohttp.ClientSession(connector=connector) as sess:
            await fau_login.login(sess)
            async with sess.get(f"{STUDON_URL}/ilias.php?baseClass=ilDashboardGUI&cmd=show") as resp:
                soup = IliasSoup(soupify(await resp.read()), str(resp.url))
            return IliasPage.is_logged_in(soup)

    return asyncio.run(run())


def pferd_main(config: str) -> None:
    """Entry point of the PFERD subprocess: FAU login + files-only filter patched in."""
    import PFERD.__main__
    from PFERD.crawl.ilias import ilias_web_crawler
    from PFERD.crawl.ilias.shibboleth_login import ShibbolethLogin
    from PFERD.logging import log

    from . import fau_login

    async def login(self, sess):  # type: ignore[no-untyped-def]
        await fau_login.login(sess)

    ShibbolethLogin.login = login

    crawler = ilias_web_crawler.IliasWebCrawler
    original = crawler._handle_ilias_element

    async def handle(self, parent_path, element, *args, **kwargs):  # type: ignore[no-untyped-def]
        # StudOn plugins (FAU-tv series, livestreams, exercise registration) are not folders, but
        # PFERD guesses "folder" for them and then fails to open them, aborting the whole course.
        if element.type.value not in ALLOWED_TYPES or "ilObjPluginDispatchGUI" in element.url:
            log.explain(f"Skipping {element.type.value} {element.name!r} (files only)")
            return None
        return await original(self, parent_path, element, *args, **kwargs)

    crawler._handle_ilias_element = handle

    sys.argv = ["pferd", "--config", config, "--report"]
    PFERD.__main__.main()

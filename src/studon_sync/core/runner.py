"""Runs PFERD for the enabled courses (sync or listing only) and summarizes what changed."""

import asyncio
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path, PurePath, PurePosixPath
from typing import Callable, Optional

from ..i18n import t
from . import logclean, paths
from . import settings as settings_mod
from .courses import STUDON_URL
from .locking import FileLock
from .filestate import DOWNLOADING, CourseState, RunSummary, plan
from .settings import Course

# Only files: containers (folders, sessions, the course info tab) are entered to find them.
ALLOWED_TYPES = {"file", "folder", "meeting", "info_tab"}

MODE_ENV = "STUDON_SYNC_MODE"  # "sync" or "list" (crawl without downloading, to refresh the file tree)


@dataclass
class CourseResult:
    course: Course
    summary: RunSummary = field(default_factory=RunSummary)
    errors: list[str] = field(default_factory=list)


@dataclass
class SyncResult:
    ok: bool
    log_path: Path
    courses: list[CourseResult] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def added(self) -> int:
        return sum(len(c.summary.added) for c in self.courses)

    @property
    def changed(self) -> int:
        return sum(len(c.summary.updated) + len(c.summary.kept_edited) for c in self.courses)

    @property
    def kept_edited(self) -> int:
        return sum(len(c.summary.kept_edited) for c in self.courses)


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
            # Whether a file is (re)downloaded is decided by filestate.decide(); this is only the fallback.
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


def is_running() -> bool:
    lock = FileLock(paths.lock_file())
    if lock.acquire():
        lock.release()
        return False
    return True


_RUNNING = re.compile(r"^Running crawl:studon-(\d+)")
_LOGIN_ERROR = re.compile(r"LoginError: (.*)$")


def login_failures(lines: list[str]) -> dict[str, str]:
    """ref_id -> login error message, from PFERD's output (errors are printed under 'Running crawl:...')."""
    failures: dict[str, str] = {}
    current = None
    for line in lines:
        if m := _RUNNING.match(line):
            current = m.group(1)
        elif current and (m := _LOGIN_ERROR.search(line)):
            failures.setdefault(current, m.group(1).strip())
    return failures


def _crawl_errors(course: Course, started: datetime, login_failed: Optional[str]) -> list[str]:
    if login_failed:
        return [t("err.course_login_failed", err=login_failed)]
    report = Path(course.target_dir).expanduser() / ".report"
    if not report.exists() or report.stat().st_mtime < started.timestamp():
        return [t("err.course_incomplete")]
    return json.loads(report.read_text(encoding="utf-8")).get("encountered_errors", [])


def run_sync(
    on_line: Callable[[str], None] = lambda line: None,
    ref_ids: Optional[list[str]] = None,
    list_only: bool = False,
) -> SyncResult:
    """Syncs (or with list_only: only lists) the enabled courses, or the given ones.

    `on_line` receives every output line (also written to the log)."""
    settings = settings_mod.load()
    started = datetime.now()
    log_path = paths.log_dir() / f"{'list' if list_only else 'sync'}-{started:%Y%m%d-%H%M%S}.log"
    if ref_ids is None:
        courses = [c for c in settings.courses if c.enabled]
    else:
        courses = [c for c in settings.courses if c.ref_id in ref_ids]

    lock = FileLock(paths.lock_file())
    if not lock.acquire():
        return SyncResult(False, log_path, error=t("err.busy"))
    try:
        with log_path.open("w", encoding="utf-8") as log:

            def out(line: str) -> None:
                log.write(line + "\n")
                log.flush()
                on_line(line)

            out(f"=== StudOn {'list' if list_only else 'sync'} {started:%Y-%m-%d %H:%M:%S} ===")
            if not courses:
                out(t("err.no_courses"))
                return SyncResult(False, log_path, error=t("err.no_courses"))

            config = paths.pferd_config_file()
            config.write_text(build_pferd_config(courses), encoding="utf-8")
            for course in courses:
                root = Path(course.target_dir).expanduser()
                root.mkdir(parents=True, exist_ok=True)
                CourseState(root).start_journal()

            proc = subprocess.Popen(
                _pferd_command(config),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env={
                    **os.environ,
                    "COLUMNS": "200",
                    "PYTHONIOENCODING": "utf-8",
                    MODE_ENV: "list" if list_only else "sync",
                },
            )
            assert proc.stdout is not None
            output: list[str] = []
            for line in proc.stdout:
                line = line.rstrip("\n")
                output.append(line)
                if not line.startswith(("Not deleted", "  Not deleted")):  # never deleted anyway
                    out(line)
            code = proc.wait()
            failed_login = login_failures(output)

            result = SyncResult(code == 0, log_path)
            for course in courses:
                cr = CourseResult(course, errors=_crawl_errors(course, started, failed_login.get(course.ref_id)))
                state = CourseState(Path(course.target_dir).expanduser())
                cr.summary = state.apply_journal(crawl_ok=code == 0 and not cr.errors, started=started)
                result.ok = result.ok and not cr.errors
                result.courses.append(cr)

            if not list_only:
                _write_summary(result, out)
    finally:
        lock.release()

    try:
        logclean.clean_logs()
    except Exception:  # cleanup must never fail a sync
        pass

    if not list_only:
        settings = settings_mod.load()  # reload: the UI may have changed settings meanwhile
        settings.last_sync = datetime.now().isoformat(timespec="seconds")
        settings.last_sync_ok = result.ok
        settings_mod.save(settings)
    return result


def _write_summary(result: SyncResult, out: Callable[[str], None]) -> None:
    out("")
    out(t("sum.header"))
    for cr in result.courses:
        s = cr.summary
        out(t("sum.course", title=cr.course.title, target=cr.course.target_dir))
        out(t("sum.counts", added=len(s.added), changed=len(s.updated)))
        for p in s.added:
            out(f"    + {p}")
        for p in s.updated:
            out(f"    ~ {p}")
        for p, alt in s.kept_edited:
            out(t("sum.kept_edited", path=p, alt=alt))
        if s.pending:
            out(t("sum.pending", n=len(s.pending)))
        for p in s.removed_remote:
            out(t("sum.removed_remote", path=p))
        if cr.errors:
            out(t("sum.errors", n=len(cr.errors)))
            for e in cr.errors:
                out(f"    ! {e}")
    out(t("sum.ok" if result.ok else "sum.failed", log=result.log_path))


def test_login() -> bool:
    """Checks the saved session, logging in only if needed. Raises LoginError."""

    async def run() -> bool:
        import ssl

        import aiohttp
        import certifi

        from . import session

        session.reset()
        connector = aiohttp.TCPConnector(ssl=ssl.create_default_context(cafile=certifi.where()))
        async with aiohttp.ClientSession(
            connector=connector, cookie_jar=session.shared_jar(), requote_redirect_url=False
        ) as sess:
            await session.ensure_logged_in(sess)
            return True

    return asyncio.run(run())


def pferd_main(config: str) -> None:
    """Entry point of the PFERD subprocess: FAU login, files-only filter and our download decisions."""
    import PFERD.__main__
    from PFERD.crawl import crawler as crawler_mod
    from PFERD.crawl.ilias import ilias_web_crawler
    from PFERD.crawl.ilias.shibboleth_login import ShibbolethLogin
    from PFERD.logging import log
    from PFERD.output_dir import OnConflict, Redownload

    from PFERD.crawl.http_crawler import HttpCrawler
    from PFERD.crawl.ilias.kit_ilias_html import IliasElementType, IliasPage

    from . import session

    async def login(self, sess):  # type: ignore[no-untyped-def]
        await session.ensure_logged_in(sess)

    ShibbolethLogin.login = login

    # All crawlers share one cookie jar (with domains), saved centrally instead of PFERD's
    # per-course .cookies files; so one login serves every course of the run (and later runs).
    def load_cookies(self):  # type: ignore[no-untyped-def]
        self._cookie_jar = session.shared_jar()

    def save_cookies(self):  # type: ignore[no-untyped-def]
        session.save_jar()

    HttpCrawler._load_cookies = load_cookies
    HttpCrawler._save_cookies = save_cookies

    # StudOn plugins (FAU-tv, livestream, exercise registration): classify quietly as a type we
    # skip, instead of PFERD's "unexpected HTML structure ... Defaulting to FOLDER" warning.
    original_find_type = IliasPage._find_type_for_element

    def find_type(element_name, url, icon_for_element):  # type: ignore[no-untyped-def]
        if "ilObjPluginDispatchGUI" in url:
            return IliasElementType.BOOKING
        return original_find_type(element_name, url, icon_for_element)

    IliasPage._find_type_for_element = staticmethod(find_type)

    ilias = ilias_web_crawler.IliasWebCrawler
    original_handle = ilias._handle_ilias_element

    async def handle(self, parent_path, element, *args, **kwargs):  # type: ignore[no-untyped-def]
        # StudOn plugins (FAU-tv series, livestreams, exercise registration) are not folders, but
        # PFERD guesses "folder" for them and then fails to open them, aborting the whole course.
        if element.type.value not in ALLOWED_TYPES or "ilObjPluginDispatchGUI" in element.url:
            log.explain(f"Skipping {element.type.value} {element.name!r} (files only)")
            return None
        return await original_handle(self, parent_path, element, *args, **kwargs)

    ilias._handle_ilias_element = handle

    list_only = os.environ.get(MODE_ENV) == "list"
    courses = {c.ref_id: c for c in settings_mod.load().courses}
    states: dict[str, CourseState] = {}
    original_download = crawler_mod.Crawler.download

    async def download(self, path, *, etag_differs=None, mtime=None, redownload=None, on_conflict=None):  # type: ignore[no-untyped-def]
        m = re.search(r"studon-(\d+)$", self.name)
        course = courses.get(m.group(1)) if m else None
        if course is None:
            return await original_download(
                self, path, etag_differs=etag_differs, mtime=mtime, redownload=redownload, on_conflict=on_conflict
            )
        root = Path(course.target_dir).expanduser()
        state = states.setdefault(course.ref_id, CourseState(root))
        rel = str(PurePosixPath(*PurePath(path).parts))
        remote = mtime.replace(microsecond=0).isoformat() if mtime else None

        if list_only:
            state.log(path=rel, action="seen", remote_mtime=remote)
            return None

        action, target = plan(state, rel, remote, course.selection, course.new_files)
        if action not in DOWNLOADING:
            return None
        return await original_download(
            self, PurePath(target), mtime=mtime, redownload=Redownload.ALWAYS, on_conflict=OnConflict.NO_DELETE
        )

    crawler_mod.Crawler.download = download

    sys.argv = ["pferd", "--config", config, "--report"]
    PFERD.__main__.main()

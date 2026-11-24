"""
One StudOn login, shared by all course crawlers and reused across runs while it is valid.

FAU rejects a TOTP code that was already used, so logging in once per course (what PFERD
does with its per-course, domain-less cookie files) fails as soon as two logins land in the
same 30 s window. Instead all crawlers of a run share ONE aiohttp cookie jar, which is stored
(with domains) in the per-user config dir and checked with a single request before any login.
Logins are serialized across processes (scheduled job, "sync now", "test login").
"""

import asyncio
import os
from typing import Optional

import aiohttp

from ..i18n import t
from . import fau_login, paths
from .courses import STUDON_URL
from .locking import FileLock

_jar: Optional[aiohttp.CookieJar] = None
_loaded_mtime = 0.0
_lock: Optional[asyncio.Lock] = None


def reset() -> None:
    """Forget the in-memory jar/lock (they belong to one event loop; call before a new asyncio.run)."""
    global _jar, _lock, _loaded_mtime
    _jar, _lock, _loaded_mtime = None, None, 0.0


def session_file():  # type: ignore[no-untyped-def]
    return paths.config_dir() / "session.cookies"


def shared_jar() -> aiohttp.CookieJar:
    """The process-wide jar, loaded from the last run if present."""
    global _jar
    if _jar is None:
        _jar = aiohttp.CookieJar()
        _reload_if_newer()
    return _jar


def _reload_if_newer() -> None:
    """Picks up a login another process saved after we loaded the jar."""
    global _loaded_mtime
    path = session_file()
    if _jar is None or not path.exists() or path.stat().st_mtime <= _loaded_mtime:
        return
    _jar.clear()
    try:
        _jar.load(path)
    except Exception:
        _jar.clear()
    _loaded_mtime = path.stat().st_mtime


def save_jar() -> None:
    global _loaded_mtime
    if _jar is None:
        return
    path = session_file()
    _jar.save(path)
    os.chmod(path, 0o600)
    _loaded_mtime = path.stat().st_mtime


async def is_logged_in(sess: aiohttp.ClientSession) -> bool:
    from PFERD.crawl.ilias.kit_ilias_html import IliasPage, IliasSoup
    from PFERD.utils import soupify

    async with sess.get(f"{STUDON_URL}/ilias.php?baseClass=ilDashboardGUI&cmd=show") as resp:
        soup = IliasSoup(soupify(await resp.read()), str(resp.url))
    return IliasPage.is_logged_in(soup)


async def ensure_logged_in(sess: aiohttp.ClientSession) -> None:
    """Makes `sess` (which must use shared_jar()) logged in, logging in only if really needed."""
    global _lock
    if _lock is None:
        _lock = asyncio.Lock()
    async with _lock:
        with FileLock(paths.config_dir() / "login.lock"):
            _reload_if_newer()
            if await is_logged_in(sess):  # another crawler/run logged in meanwhile
                print(t("log.reuse_login"), flush=True)
                return
            print(t("log.new_login"), flush=True)
            await fau_login.login(sess)
            if not await is_logged_in(sess):
                raise fau_login.LoginError(t("err.not_logged_in"))
            save_jar()

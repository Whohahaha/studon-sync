"""TOTP step guard, shared session jar, login-failure parsing and file lock (no network)."""

import asyncio
from pathlib import Path

import pyotp
import pytest
from yarl import URL

from studon_sync.core import fau_login, paths, session
from studon_sync.core.locking import FileLock
from studon_sync.core.runner import login_failures

SECRET = pyotp.random_base32()


@pytest.fixture(autouse=True)
def config_dir(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(paths, "config_dir", lambda: tmp_path)
    session.reset()
    return tmp_path


class FakeClock:
    def __init__(self, start: float) -> None:
        self.now = start

    def time(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.now += max(0, seconds)


@pytest.fixture
def clock(monkeypatch) -> FakeClock:
    c = FakeClock(1_800_000_010.0)  # 10 s into a 30 s window
    monkeypatch.setattr(fau_login.time, "time", c.time)
    monkeypatch.setattr(fau_login.asyncio, "sleep", c.sleep)
    return c


def test_totp_never_submits_the_same_window_twice(clock):
    first = asyncio.run(fau_login._Totp(SECRET).code())
    clock.now += 5  # same window, e.g. the next course crawler or another process
    second = asyncio.run(fau_login._Totp(SECRET).code())
    assert clock.now >= 1_800_000_030  # waited for the next window
    assert second == pyotp.TOTP(SECRET).at(1_800_000_030)


def test_totp_no_wait_in_a_new_window(clock):
    asyncio.run(fau_login._Totp(SECRET).code())
    clock.now += 40
    before = clock.now
    asyncio.run(fau_login._Totp(SECRET).code())
    assert clock.now == before


def test_shared_jar_survives_runs_with_domains(config_dir):
    async def first_run() -> None:
        jar = session.shared_jar()
        jar.update_cookies({"PHPSESSID": "abc"}, URL("https://www.studon.fau.de/studon/"))
        jar.update_cookies({"SimpleSAMLSessionID": "idp"}, URL("https://www.sso.uni-erlangen.de/"))
        session.save_jar()

    async def next_run() -> dict:
        jar = session.shared_jar()
        return {
            "studon": {m.key for m in jar.filter_cookies(URL("https://www.studon.fau.de/studon/x")).values()},
            "idp": {m.key for m in jar.filter_cookies(URL("https://www.sso.uni-erlangen.de/simplesaml/")).values()},
        }

    asyncio.run(first_run())
    session.reset()
    got = asyncio.run(next_run())
    assert got == {"studon": {"PHPSESSID"}, "idp": {"SimpleSAMLSessionID"}}
    assert oct((config_dir / "session.cookies").stat().st_mode)[-3:] == "600"


def test_login_failures_are_attributed_to_their_course():
    out = [
        "Running crawl:studon-111",
        "Crawled     '.'",
        "Running crawl:studon-222",
        "Error An unexpected exception occurred",
        "studon_sync.core.fau_login.LoginError: TOTP 验证码被拒绝。",
        "Running crawl:studon-333",
    ]
    assert login_failures(out) == {"222": "TOTP 验证码被拒绝。"}


def test_file_lock_is_exclusive(tmp_path):
    a, b = FileLock(tmp_path / "x.lock"), FileLock(tmp_path / "x.lock")
    assert a.acquire()
    assert not b.acquire()
    a.release()
    assert b.acquire()
    b.release()

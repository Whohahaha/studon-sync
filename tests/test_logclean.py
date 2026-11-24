"""Log cleanup policy."""

import os
from pathlib import Path

from studon_sync.core.logclean import KEEP_RECENT, clean_logs

DAY = 86400
NOW = 1_800_000_000.0


def make(d: Path, name: str, result: str, days_old: float) -> Path:
    p = d / name
    p.write_text(f"=== StudOn sync ===\n...\n{result}\n", encoding="utf-8")
    ts = NOW - days_old * DAY
    os.utime(p, (ts, ts))
    return p


def test_policy(tmp_path: Path) -> None:
    ok_old = make(tmp_path, "sync-20261101-080000.log", "结果：成功（日志：x）", 20)
    fail_old = make(tmp_path, "sync-20261102-080000.log", "结果：失败（日志：x）", 19)
    fail_ancient = make(tmp_path, "sync-20260801-080000.log", "结果：失败（日志：x）", 100)
    crashed = make(tmp_path, "sync-20261103-080000.log", "Traceback ...", 18)
    listing = make(tmp_path, "list-20261104-080000.log", "", 17)
    recent = [make(tmp_path, f"sync-202611{10 + i}-080000.log", "结果：成功（日志：x）", 10 - i) for i in range(KEEP_RECENT)]
    dbg_old = make(tmp_path, "login-debug-20261001-080000.html", "", 40)
    dbg_new = make(tmp_path, "login-debug-20261120-080000.html", "", 4)

    deleted = set(clean_logs(tmp_path, now=NOW))

    assert deleted == {ok_old, fail_ancient, listing, dbg_old}
    for kept in [fail_old, crashed, dbg_new, *recent]:
        assert kept.exists()


def test_few_logs_untouched(tmp_path: Path) -> None:
    logs = [make(tmp_path, f"sync-2026110{i}-080000.log", "结果：成功（日志：x）", 5) for i in range(KEEP_RECENT)]
    assert clean_logs(tmp_path, now=NOW) == []
    assert all(p.exists() for p in logs)

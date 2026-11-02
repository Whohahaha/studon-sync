"""Download decisions and protection of edited files, simulated without network or PFERD."""

import os
from datetime import datetime
from pathlib import Path

import pytest

from studon_sync.core.filestate import DOWNLOADING, Action, CourseState, is_selected, plan

T1 = "2026-11-01T10:00:00"
T2 = "2026-11-05T09:30:00"


def sync(root: Path, remote: dict[str, tuple[str, bytes]], selection=None, new_files="auto", fail=()):
    """One simulated sync run: remote maps path -> (mtime, content). Returns (actions, summary)."""
    state = CourseState(root)
    state.start_journal()
    actions = {}
    for rel, (mtime, content) in remote.items():
        action, target = plan(state, rel, mtime, selection or {}, new_files)
        actions[rel] = action
        if action in DOWNLOADING and rel not in fail:
            dest = root / target
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(content)
            ts = datetime.fromisoformat(mtime).timestamp()
            os.utime(dest, (ts, ts))  # like PFERD
    summary = CourseState(root).apply_journal(crawl_ok=True, started=datetime.now())
    return actions, summary


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path / "course"


def test_new_file_is_downloaded_and_recorded(root):
    actions, summary = sync(root, {"slides/01.pdf": (T1, b"v1")})
    assert actions["slides/01.pdf"] == Action.DOWNLOAD_NEW
    assert summary.added == ["slides/01.pdf"]
    assert CourseState(root).files["slides/01.pdf"]["remote_mtime"] == T1


def test_unchanged_remote_is_skipped(root):
    sync(root, {"a.pdf": (T1, b"v1")})
    actions, summary = sync(root, {"a.pdf": (T1, b"v1")})
    assert actions["a.pdf"] == Action.SKIP_UNCHANGED
    assert not summary.added and not summary.updated


def test_untouched_file_is_replaced_and_old_copy_kept(root):
    sync(root, {"a.pdf": (T1, b"v1")})
    actions, summary = sync(root, {"a.pdf": (T2, b"v2")})
    assert actions["a.pdf"] == Action.REPLACE
    assert (root / "a.pdf").read_bytes() == b"v2"
    assert summary.updated == ["a.pdf"]
    backups = list((root / ".studon-sync" / "versions").rglob("a.pdf"))
    assert [b.read_bytes() for b in backups] == [b"v1"]


def test_edited_file_is_never_overwritten(root):
    sync(root, {"notes/a.pdf": (T1, b"v1")})
    (root / "notes/a.pdf").write_bytes(b"v1 + my annotations")
    actions, summary = sync(root, {"notes/a.pdf": (T2, b"v2")})
    assert actions["notes/a.pdf"] == Action.SAVE_ALT
    assert (root / "notes/a.pdf").read_bytes() == b"v1 + my annotations"
    assert (root / "notes/a (StudOn 2026-11-05).pdf").read_bytes() == b"v2"
    assert summary.kept_edited == [("notes/a.pdf", "notes/a (StudOn 2026-11-05).pdf")]
    # same remote version again: nothing new
    actions, _ = sync(root, {"notes/a.pdf": (T2, b"v2")})
    assert actions["notes/a.pdf"] == Action.SKIP_UNCHANGED
    # yet another version: still kept, second copy
    actions, _ = sync(root, {"notes/a.pdf": ("2026-11-05T18:00:00", b"v3")})
    assert actions["notes/a.pdf"] == Action.SAVE_ALT
    assert (root / "notes/a (StudOn 2026-11-05 2).pdf").read_bytes() == b"v3"
    assert (root / "notes/a.pdf").read_bytes() == b"v1 + my annotations"


def test_deleted_by_user_stays_deleted_until_forgotten(root):
    sync(root, {"a.pdf": (T1, b"v1")})
    (root / "a.pdf").unlink()
    actions, summary = sync(root, {"a.pdf": (T1, b"v1")})
    assert actions["a.pdf"] == Action.SKIP_DELETED
    assert not (root / "a.pdf").exists()
    assert summary.deleted_locally == ["a.pdf"]
    CourseState(root).forget("a.pdf")
    actions, _ = sync(root, {"a.pdf": (T1, b"v1")})
    assert actions["a.pdf"] == Action.DOWNLOAD_NEW
    assert (root / "a.pdf").exists()


def test_removed_on_studon_is_kept_locally(root):
    sync(root, {"a.pdf": (T1, b"v1"), "b.pdf": (T1, b"b")})
    _, summary = sync(root, {"a.pdf": (T1, b"v1")})
    assert summary.removed_remote == ["b.pdf"]
    assert (root / "b.pdf").exists()
    assert CourseState(root).remote["b.pdf"]["removed"]


def test_selection_and_defaults():
    sel = {"Exercise": False, "Exercise/keep.pdf": True}
    assert not is_selected("Exercise/sheet1.pdf", sel, "auto", known=False)
    assert is_selected("Exercise/keep.pdf", sel, "auto", known=False)
    assert is_selected("Lecture/01.pdf", sel, "auto", known=False)
    assert not is_selected("Info/Description.html", {}, "auto", known=False)
    assert not is_selected("Lecture/new.pdf", {}, "review", known=False)
    assert is_selected("Lecture/old.pdf", {}, "review", known=True)


def test_unselected_and_review_pending(root):
    actions, summary = sync(
        root, {"Exercise/s.pdf": (T1, b"x"), "Lecture/new.pdf": (T1, b"y")}, selection={"Exercise": False}, new_files="review"
    )
    assert actions == {"Exercise/s.pdf": Action.SKIP_UNSELECTED, "Lecture/new.pdf": Action.SKIP_UNSELECTED}
    assert summary.pending == ["Lecture/new.pdf"]  # explicitly excluded files are not "pending"
    assert not (root / "Exercise").exists()


def test_existing_files_are_adopted(root):
    root.mkdir()
    clean, edited = root / "clean.pdf", root / "edited.pdf"
    for f in (clean, edited):
        f.write_bytes(b"v1")
        ts = datetime.fromisoformat(T1).timestamp()
        os.utime(f, (ts, ts))
    edited.write_bytes(b"v1 + notes")  # touched after download: mtime no longer matches StudOn
    actions, _ = sync(root, {"clean.pdf": (T1, b"v1"), "edited.pdf": (T1, b"v1")})
    assert actions == {"clean.pdf": Action.ADOPT, "edited.pdf": Action.ADOPT}
    actions, _ = sync(root, {"clean.pdf": (T2, b"v2"), "edited.pdf": (T2, b"v2")})
    assert actions == {"clean.pdf": Action.REPLACE, "edited.pdf": Action.SAVE_ALT}
    assert edited.read_bytes() == b"v1 + notes"


def test_failed_replace_restores_previous_copy(root):
    sync(root, {"a.pdf": (T1, b"v1")})
    sync(root, {"a.pdf": (T2, b"v2")}, fail={"a.pdf"})
    assert (root / "a.pdf").read_bytes() == b"v1"

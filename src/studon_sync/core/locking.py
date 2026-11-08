"""Cross-process file locks (fcntl on macOS/Linux, msvcrt on Windows)."""

import os
from pathlib import Path
from typing import Optional


class FileLock:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._fd: Optional[int] = None

    def acquire(self, blocking: bool = False) -> bool:
        self._fd = os.open(self._path, os.O_RDWR | os.O_CREAT)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self._fd, msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._fd, fcntl.LOCK_EX if blocking else fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(self._fd)
            self._fd = None
            return False
        return True

    def release(self) -> None:
        if self._fd is not None:
            os.close(self._fd)  # closing releases the lock
            self._fd = None

    def __enter__(self) -> "FileLock":
        self.acquire(blocking=True)
        return self

    def __exit__(self, *exc: object) -> None:
        self.release()

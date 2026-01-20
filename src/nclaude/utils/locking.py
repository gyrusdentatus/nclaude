"""File locking utilities for atomic operations."""

import fcntl
from contextlib import contextmanager
from pathlib import Path
from typing import Generator


@contextmanager
def file_lock(lock_path: Path) -> Generator[None, None, None]:
    """Context manager for exclusive file locking.

    Args:
        lock_path: Path to the lock file

    Yields:
        None - just provides locked context
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.touch()

    with open(lock_path, "r") as lock_fd:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)

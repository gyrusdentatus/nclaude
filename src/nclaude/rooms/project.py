"""Project-scoped room (default nclaude behavior)."""

from pathlib import Path
from typing import Optional

from ..config import get_base_dir
from ..storage import FileStorage, get_storage
from ..storage.base import StorageBackend
from .base import Room


class ProjectRoom(Room):
    """Room scoped to a git project.

    Path: /tmp/nclaude/<repo-name>/
    All worktrees of the same repo share the same room.
    """

    def __init__(
        self,
        dir_override: Optional[str] = None,
        storage_backend: str = "file",
    ):
        """Initialize project room.

        Args:
            dir_override: Override directory (--dir flag)
            storage_backend: Storage backend to use
        """
        self._base_dir = get_base_dir(override=dir_override, use_global=False)
        self._storage_backend = storage_backend
        self._storage: Optional[StorageBackend] = None

    @property
    def name(self) -> str:
        """Room name is the project/repo name."""
        return self._base_dir.name

    @property
    def path(self) -> Path:
        """Path to room storage."""
        return self._base_dir

    @property
    def storage(self) -> StorageBackend:
        """Get or create storage backend."""
        if self._storage is None:
            if self._storage_backend == "file":
                self._storage = FileStorage(base_dir=self._base_dir)
            else:
                self._storage = get_storage(
                    self._storage_backend, base_dir=self._base_dir
                )
        return self._storage

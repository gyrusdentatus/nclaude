"""Global room for cross-project messaging."""

from pathlib import Path
from typing import Optional

from ..storage import FileStorage, get_storage
from ..storage.base import StorageBackend
from .base import Room


class GlobalRoom(Room):
    """Global room shared across all projects.

    Path: ~/.nclaude/
    Used with --global flag for cross-project coordination.
    """

    def __init__(self, storage_backend: str = "file"):
        """Initialize global room.

        Args:
            storage_backend: Storage backend to use
        """
        self._base_dir = Path.home() / ".nclaude"
        self._storage_backend = storage_backend
        self._storage: Optional[StorageBackend] = None

    @property
    def name(self) -> str:
        """Room name is 'global'."""
        return "global"

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

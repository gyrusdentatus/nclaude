"""Storage backends for nclaude messages."""

from .base import Message, StorageBackend
from .file import FileStorage

__all__ = ["Message", "StorageBackend", "FileStorage", "get_storage"]


def get_storage(backend: str = "file", **kwargs) -> StorageBackend:
    """Factory function to get a storage backend.

    Args:
        backend: Storage type ("file" or "sqlite")
        **kwargs: Backend-specific arguments

    Returns:
        StorageBackend instance
    """
    if backend == "file":
        return FileStorage(**kwargs)
    elif backend == "sqlite":
        from .sqlite import SQLiteStorage
        return SQLiteStorage(**kwargs)
    else:
        raise ValueError(f"Unknown storage backend: {backend}")

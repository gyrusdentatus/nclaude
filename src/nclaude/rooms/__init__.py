"""Room abstractions for nclaude."""

from .base import Room
from .project import ProjectRoom
from .global_room import GlobalRoom

__all__ = ["Room", "ProjectRoom", "GlobalRoom", "get_room"]


def get_room(
    use_global: bool = False,
    dir_override: str = None,
    storage_backend: str = "file",
) -> Room:
    """Get the appropriate room instance.

    Args:
        use_global: If True, use global room
        dir_override: Override directory (--dir flag)
        storage_backend: Storage backend to use

    Returns:
        Room instance
    """
    if use_global:
        return GlobalRoom(storage_backend=storage_backend)
    return ProjectRoom(dir_override=dir_override, storage_backend=storage_backend)

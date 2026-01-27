"""Alias command implementation - delegates to aqua_bridge."""

from typing import Any, Dict, Optional

from ..aqua_bridge import create_alias, delete_alias, get_aliases, get_session_id


def cmd_alias(
    name: Optional[str] = None,
    target: Optional[str] = None,
    delete: bool = False,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Manage session aliases.

    Args:
        name: Alias name (e.g., "k8s", "main")
        target: Session ID to alias (e.g., "nclaude/main-1")
        delete: If True, delete the alias
        session_id: Current session ID (used when target not provided)

    Returns:
        Dict with aliases or operation result
    """
    # List all aliases
    if name is None:
        aliases = get_aliases()
        if not aliases:
            return {"aliases": {}, "message": "No aliases set. Use: nclaude alias <name>"}
        return {"aliases": aliases}

    # Delete alias
    if delete:
        if delete_alias(name):
            return {"deleted": name}
        return {"error": f"Alias '{name}' not found"}

    # Set alias - auto-fill target from session_id if not provided
    if target:
        # Strip @ prefix if present
        target = target.lstrip("@")
    elif session_id:
        # Auto-fill from current session
        target = session_id
    else:
        # No target and no session_id - get from environment
        target = get_session_id()

    create_alias(name, target)
    return {"set": {name: target}, "usage": f"Use @{name} to message {target}"}

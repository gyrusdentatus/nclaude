"""Alias command implementation."""

from typing import Any, Dict, Optional

from ..config import load_aliases, save_aliases


def cmd_alias(
    name: Optional[str] = None,
    target: Optional[str] = None,
    delete: bool = False,
) -> Dict[str, Any]:
    """Manage session aliases.

    Args:
        name: Alias name (e.g., "k8s", "main")
        target: Session ID to alias (e.g., "cc-26146992-94a")
        delete: If True, delete the alias

    Returns:
        Dict with aliases or operation result
    """
    aliases = load_aliases()

    # List all aliases
    if name is None:
        if not aliases:
            return {"aliases": {}, "message": "No aliases set. Use: nclaude alias <name> <session-id>"}
        return {"aliases": aliases}

    # Delete alias
    if delete:
        if name in aliases:
            del aliases[name]
            save_aliases(aliases)
            return {"deleted": name}
        return {"error": f"Alias '{name}' not found"}

    # Set alias
    if target:
        # Strip @ prefix if present
        target = target.lstrip("@")
        aliases[name] = target
        save_aliases(aliases)
        return {"set": {name: target}, "usage": f"Use @{name} to message {target}"}

    # Get single alias
    if name in aliases:
        return {"alias": name, "target": aliases[name]}
    return {"error": f"Alias '{name}' not found"}

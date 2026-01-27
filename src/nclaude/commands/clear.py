"""Clear command implementation."""

from typing import Any, Dict


def cmd_clear() -> Dict[str, Any]:
    """Clear is deprecated with aqua backend.

    In a multi-agent system, clearing all messages is dangerous.
    Use `aqua` CLI directly for administrative tasks.

    Returns:
        Dict with warning
    """
    return {
        "warning": "Clear is deprecated with aqua backend",
        "hint": "Messages are now managed by aqua. Use 'aqua' CLI for admin tasks.",
        "status": "skipped",
    }

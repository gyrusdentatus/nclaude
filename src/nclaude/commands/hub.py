"""Hub commands - delegate to hub.py and client.py scripts."""

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..utils.git import get_auto_session_id


def _get_scripts_dir() -> Path:
    """Get path to scripts directory."""
    # Navigate from src/nclaude/commands/ to scripts/
    return Path(__file__).parent.parent.parent.parent / "scripts"


def cmd_hub(subcmd: str = "status") -> Dict[str, Any]:
    """Delegate to hub.py script.

    Args:
        subcmd: Hub subcommand (start, stop, status)

    Returns:
        Dict with hub status/result
    """
    hub_script = _get_scripts_dir() / "hub.py"
    if not hub_script.exists():
        return {"error": f"Hub script not found: {hub_script}"}

    proc = subprocess.run(
        ["python3", str(hub_script), subcmd],
        capture_output=True,
        text=True,
    )
    if proc.stdout:
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError:
            return {"output": proc.stdout}
    else:
        return {"error": proc.stderr}


def cmd_connect(session_id: Optional[str] = None) -> Dict[str, Any]:
    """Connect to hub.

    Args:
        session_id: Session ID to connect as

    Returns:
        Dict with connection status
    """
    client_script = _get_scripts_dir() / "client.py"
    if not client_script.exists():
        return {"error": f"Client script not found: {client_script}"}

    session_id = session_id or get_auto_session_id()

    proc = subprocess.run(
        ["python3", str(client_script), "connect", session_id],
        capture_output=True,
        text=True,
    )
    if proc.stdout:
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError:
            return {"output": proc.stdout}
    else:
        return {"error": proc.stderr}


def cmd_hsend(message: str) -> Dict[str, Any]:
    """Send message via hub (real-time).

    Args:
        message: Message to send

    Returns:
        Dict with send result
    """
    if not message:
        return {"error": "No message provided"}

    client_script = _get_scripts_dir() / "client.py"
    if not client_script.exists():
        return {"error": f"Client script not found: {client_script}"}

    proc = subprocess.run(
        ["python3", str(client_script), "send", message],
        capture_output=True,
        text=True,
    )
    if proc.stdout:
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError:
            return {"output": proc.stdout}
    else:
        return {"error": proc.stderr}


def cmd_hrecv(timeout: int = 5) -> Dict[str, Any]:
    """Receive message from hub (real-time).

    Args:
        timeout: Receive timeout in seconds

    Returns:
        Dict with received message
    """
    client_script = _get_scripts_dir() / "client.py"
    if not client_script.exists():
        return {"error": f"Client script not found: {client_script}"}

    proc = subprocess.run(
        ["python3", str(client_script), "recv", "--timeout", str(timeout)],
        capture_output=True,
        text=True,
    )
    if proc.stdout:
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError:
            return {"output": proc.stdout}
    else:
        return {"error": proc.stderr}

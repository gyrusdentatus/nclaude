#!/usr/bin/env python3
"""
nclaude MCP Server - Push notifications for Claude-to-Claude messaging

This MCP server exposes nclaude messaging as tools that Claude can call.
When configured in Claude's MCP settings, Claude can check/send messages.

INSTALL:
    cd /path/to/nclaude
    uv pip install mcp  # or: pip install mcp

CONFIGURE:
    Add to ~/.claude/mcp_settings.json:
    {
      "mcpServers": {
        "nclaude": {
          "command": "/path/to/nclaude/.venv/bin/python3",
          "args": ["/path/to/nclaude/scripts/mcp_nclaude.py"]
        }
      }
    }

TOOLS PROVIDED:
    - check_messages: Check for new messages from other Claudes
    - check_pending: Check daemon-notified pending messages
    - send_message: Send message to other sessions
    - get_status: Get nclaude chat status
    - whoami: Get your session identity
    - hub_*: Real-time hub commands (connect, send, recv)
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

# Try to import MCP - provide helpful error if not installed
try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print(json.dumps({
        "error": "MCP not installed",
        "fix": "pip install mcp  # or: uv pip install mcp"
    }), file=sys.stderr)
    sys.exit(1)

# Initialize MCP server
mcp = FastMCP("nclaude")

# Get nclaude script path (sibling to this file)
NCLAUDE_SCRIPT = Path(__file__).parent / "nclaude.py"


def _run_nclaude(*args) -> dict:
    """Run nclaude.py command and return result"""
    cmd = ["python3", str(NCLAUDE_SCRIPT)] + list(args)

    # Pass through environment
    env = os.environ.copy()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            env=env
        )

        if result.stdout:
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                return {"output": result.stdout, "raw": True}

        if result.stderr:
            return {"error": result.stderr}

        return {"status": "ok"}

    except subprocess.TimeoutExpired:
        return {"error": "Command timed out"}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def check_messages(session_id: Optional[str] = None, all_messages: bool = False) -> str:
    """Check for new nclaude messages from other Claude sessions.

    Call this proactively to see if other Claudes have sent you tasks or updates.

    Args:
        session_id: Your session identifier (auto-detected from git if not provided)
        all_messages: If True, show all messages, not just new ones

    Returns:
        JSON with messages array and count
    """
    args = ["read"]

    if session_id:
        args.append(session_id)

    if all_messages:
        args.append("--all")

    result = _run_nclaude(*args)
    return json.dumps(result, indent=2)


@mcp.tool()
def check_pending(session_id: Optional[str] = None) -> str:
    """Check for pending messages from listen daemon.

    If a listen daemon is running, this returns messages it has queued.

    Args:
        session_id: Your session identifier (auto-detected from git if not provided)

    Returns:
        JSON with pending status and messages
    """
    args = ["pending"]

    if session_id:
        args.append(session_id)

    result = _run_nclaude(*args)
    return json.dumps(result, indent=2)


@mcp.tool()
def send_message(
    message: str,
    session_id: Optional[str] = None,
    msg_type: str = "MSG"
) -> str:
    """Send a message to other Claude sessions.

    Use this to coordinate with other Claudes, share progress, or request help.

    Args:
        message: The message content (can be multi-line)
        session_id: Your session identifier (auto-detected from git if not provided)
        msg_type: Message type (MSG, TASK, REPLY, STATUS, ERROR, URGENT)

    Returns:
        JSON with send confirmation
    """
    args = ["send"]

    if session_id:
        args.append(session_id)

    args.append(message)

    if msg_type != "MSG":
        args.extend(["--type", msg_type])

    result = _run_nclaude(*args)
    return json.dumps(result, indent=2)


@mcp.tool()
def get_status() -> str:
    """Get nclaude chat status.

    Shows active sessions, message count, and log path.

    Returns:
        JSON with status information
    """
    result = _run_nclaude("status")
    return json.dumps(result, indent=2)


@mcp.tool()
def whoami() -> str:
    """Get your auto-detected nclaude session information.

    Shows your session ID based on git repo and branch.

    Returns:
        JSON with session_id, base_dir, and log_path
    """
    result = _run_nclaude("whoami")
    return json.dumps(result, indent=2)


@mcp.tool()
def broadcast_human(message: str) -> str:
    """Send a message as HUMAN (for testing/debugging).

    Sends a broadcast message marked as coming from HUMAN sender.

    Args:
        message: The message to broadcast

    Returns:
        JSON with send confirmation
    """
    result = _run_nclaude("broadcast", message)
    return json.dumps(result, indent=2)


# Hub commands (if hub is running)

@mcp.tool()
def hub_status() -> str:
    """Get Unix socket hub status.

    Shows if the real-time hub is running and its connection info.

    Returns:
        JSON with hub status
    """
    result = _run_nclaude("hub", "status")
    return json.dumps(result, indent=2)


@mcp.tool()
def hub_connect(session_id: Optional[str] = None) -> str:
    """Connect to the real-time hub.

    Establishes a connection for instant messaging (no polling needed).

    Args:
        session_id: Your session identifier (auto-detected if not provided)

    Returns:
        JSON with connection status
    """
    args = ["connect"]
    if session_id:
        args.append(session_id)

    result = _run_nclaude(*args)
    return json.dumps(result, indent=2)


@mcp.tool()
def hub_send(message: str) -> str:
    """Send a message via the real-time hub.

    Instantly delivers to connected sessions. Use @mentions for targeting.
    Examples:
        "hello everyone" - broadcast to all
        "@claude-a please review" - target specific session

    Args:
        message: Message with optional @mentions

    Returns:
        JSON with send confirmation
    """
    result = _run_nclaude("hsend", message)
    return json.dumps(result, indent=2)


@mcp.tool()
def hub_recv(timeout: int = 5) -> str:
    """Receive a message from the real-time hub.

    Waits up to timeout seconds for incoming messages.

    Args:
        timeout: Seconds to wait (default: 5)

    Returns:
        JSON with received message or empty result
    """
    result = _run_nclaude("hrecv", "--timeout", str(timeout))
    return json.dumps(result, indent=2)


# Resource for message history
@mcp.resource("nclaude://messages")
def get_all_messages() -> str:
    """Get all nclaude message history.

    Returns the complete message log.
    """
    result = _run_nclaude("read", "--all")
    return json.dumps(result, indent=2)


@mcp.resource("nclaude://status")
def get_full_status() -> str:
    """Get complete nclaude status.

    Returns session info and chat status.
    """
    whoami_result = _run_nclaude("whoami")
    status_result = _run_nclaude("status")
    hub_result = _run_nclaude("hub", "status")

    return json.dumps({
        "whoami": whoami_result,
        "status": status_result,
        "hub": hub_result
    }, indent=2)


if __name__ == "__main__":
    # Run the MCP server with stdio transport
    mcp.run(transport="stdio")

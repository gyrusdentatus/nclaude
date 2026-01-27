"""CLI argument parsing and command dispatch for nclaude.

nclaude is a thin wrapper around aqua for Claude Code integration.
All core functionality delegates to aqua_bridge.
"""

import argparse
import json
import sys
from typing import Any, Dict, Optional

from . import __version__
from .aqua_bridge import get_session_id
from .commands import (
    cmd_send,
    cmd_read,
    cmd_check,
    cmd_status,
    cmd_clear,
    cmd_whoami,
    cmd_pending,
    cmd_listen,
    cmd_watch,
    cmd_pair,
    cmd_unpair,
    cmd_peers,
    cmd_broadcast,
    cmd_chat,
    cmd_hub,
    cmd_connect,
    cmd_hsend,
    cmd_hrecv,
    cmd_alias,
    cmd_wait,
    cmd_wake,
    cmd_sessions,
)
from .transports.gchat import GChatTransport


def show_help() -> None:
    """Human-friendly help output."""
    help_text = """
nclaude - Claude-to-Claude Chat (powered by aqua)
==================================================

QUICK START:
  nclaude send "hello"              # Send message
  nclaude check                     # Read unread messages
  nclaude watch                     # Live message feed

COMMANDS:
  send <msg>        Send message
  check             Read all unread messages
  read              Read messages (with filtering options)
  wait [timeout]    Block until message arrives (default 30s)
  watch             Live message feed
  status            Show session and aqua status
  whoami            Show current session ID
  alias [name] [id] Manage session aliases

COORDINATION (via aqua):
  These commands delegate to aqua CLI for multi-agent coordination.
  Run 'aqua init' to enable coordination in your project.

FLAGS:
  --global, -g      Use global room (~/.aqua/)
  --to @NAME        Send to specific recipient
  --type TYPE       Message type: MSG|TASK|REPLY|STATUS|URGENT|ERROR
  --gchat           Also send/check via Google Chat
  --timeout SECS    Timeout for watch/wait (default 60)
  --limit N         Max messages to return
  --quiet, -q       Minimal output

EXAMPLES:
  nclaude send "Starting work on auth"
  nclaude send "Need help" --to @frontend
  nclaude check
  nclaude watch --timeout 0          # Watch forever
  nclaude alias k8s                  # Create alias for current session
  nclaude send "hello" --global      # Global room

SESSION ID FORMAT:
  New: {repo}/{branch}-{instance}    (e.g., nclaude/main-1)
  Old: cc-{12chars}                  (deprecated)

For aqua coordination commands:
  aqua join          # Join project as agent
  aqua task add      # Add task to queue
  aqua task claim    # Claim next task
  aqua lock <file>   # Acquire file lock
  aqua status        # Full coordination status
"""
    print(help_text)


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="nclaude",
        description="Claude-to-Claude messaging (powered by aqua)",
        add_help=False,
    )
    parser.add_argument(
        "-h", "--help", action="store_true", help="Show help message"
    )
    parser.add_argument(
        "-v", "--version", action="store_true", help="Show version"
    )
    parser.add_argument(
        "-g", "--global", dest="use_global", action="store_true",
        help="Use global room (~/.aqua/)"
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="Minimal output"
    )
    parser.add_argument(
        "--all", action="store_true", help="Show all messages"
    )
    parser.add_argument(
        "--type", dest="msg_type", default="MSG",
        help="Message type: MSG|TASK|REPLY|STATUS|URGENT|ERROR"
    )
    parser.add_argument(
        "--timeout", type=int, default=60,
        help="Timeout for watch/listen commands"
    )
    parser.add_argument(
        "--interval", type=float, default=1.0,
        help="Polling interval for watch/listen commands"
    )
    parser.add_argument(
        "--history", type=int, default=0,
        help="Number of recent messages to show in watch"
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Maximum messages to return"
    )
    parser.add_argument(
        "--filter", dest="filter_type", default=None,
        help="Filter by message type"
    )
    parser.add_argument(
        "--to", dest="to_recipient", default=None,
        help="Send to specific recipient (@mention)"
    )
    parser.add_argument(
        "--for-me", dest="for_me", action="store_true",
        help="Only show messages addressed to me"
    )
    parser.add_argument(
        "--all-peers", dest="all_peers", action="store_true",
        help="Broadcast to all registered peers"
    )
    parser.add_argument(
        "--delete", "-D", dest="delete", action="store_true",
        help="Delete alias"
    )
    parser.add_argument(
        "--gchat", dest="gchat", action="store_true",
        help="Also send/check via Google Chat"
    )
    parser.add_argument(
        "--gchat-only", dest="gchat_only", action="store_true",
        help="Only use Google Chat, skip local"
    )
    parser.add_argument(
        "command", nargs="?", help="Command to run"
    )
    parser.add_argument(
        "args", nargs="*", help="Command arguments"
    )

    return parser


def run_command(args: argparse.Namespace) -> Optional[Dict[str, Any]]:
    """Run a command based on parsed args."""
    cmd = args.command
    cmd_args = args.args or []

    # Command dispatch
    if cmd == "whoami":
        return cmd_whoami()

    elif cmd == "send":
        message = " ".join(cmd_args) if cmd_args else ""
        result = {}

        # Send to local unless --gchat-only
        if not args.gchat_only:
            result["local"] = cmd_send(
                message,
                args.msg_type.upper(),
                to=args.to_recipient,
                global_=args.use_global,
            )

        # Send to gchat if --gchat or --gchat-only
        if args.gchat or args.gchat_only:
            session_id = get_session_id()
            gchat = GChatTransport()
            result["gchat"] = gchat.queue_send(
                session_id, message, args.msg_type.upper(), args.to_recipient
            )

        return result if len(result) > 1 else result.get("local") or result.get("gchat")

    elif cmd == "read":
        return cmd_read(
            all_messages=args.all,
            quiet=args.quiet,
            limit=args.limit,
            msg_type=args.filter_type,
            for_me=args.for_me,
            global_=args.use_global,
        )

    elif cmd == "status":
        result = cmd_status()
        if args.gchat or args.gchat_only:
            gchat = GChatTransport()
            result["gchat"] = gchat.status()
        return result

    elif cmd == "clear":
        return cmd_clear()

    elif cmd == "pair":
        if not cmd_args:
            return {"error": "Usage: nclaude pair <project-name>"}
        return cmd_pair(cmd_args[0])

    elif cmd == "unpair":
        target = cmd_args[0] if cmd_args else None
        return cmd_unpair(target)

    elif cmd == "peers":
        return cmd_peers()

    elif cmd == "alias":
        session_id = get_session_id()
        if not cmd_args:
            return cmd_alias()
        elif len(cmd_args) == 1:
            if args.delete:
                return cmd_alias(name=cmd_args[0], delete=True)
            return cmd_alias(name=cmd_args[0], session_id=session_id)
        else:
            return cmd_alias(name=cmd_args[0], target=cmd_args[1])

    elif cmd == "broadcast":
        message = " ".join(cmd_args) if cmd_args else ""
        return cmd_broadcast(message, all_peers=args.all_peers)

    elif cmd == "pending":
        return cmd_pending()

    elif cmd == "check":
        result = {}

        # Check local unless --gchat-only
        if not args.gchat_only:
            result["local"] = cmd_check(for_me=args.for_me, global_=args.use_global)

        # Check gchat inbox if --gchat or --gchat-only
        if args.gchat or args.gchat_only:
            session_id = get_session_id()
            gchat = GChatTransport()
            inbox_msgs = gchat.read_inbox(session_id)
            result["gchat"] = {
                "messages": inbox_msgs,
                "count": len(inbox_msgs),
                "hint": "Run /nclaude:gchat sync to fetch from Google Chat",
            }

        return result if len(result) > 1 else result.get("local") or result.get("gchat")

    elif cmd == "listen":
        cmd_listen(int(args.interval))
        return None

    elif cmd == "watch":
        cmd_watch(args.timeout, args.interval, args.history, args.use_global)
        return None

    elif cmd == "wait":
        wait_timeout = int(cmd_args[0]) if cmd_args else args.timeout
        return cmd_wait(wait_timeout, args.interval, args.use_global)

    elif cmd == "hub":
        subcmd = cmd_args[0] if cmd_args else "status"
        return cmd_hub(subcmd)

    elif cmd == "connect":
        sess = cmd_args[0] if cmd_args else None
        return cmd_connect(sess)

    elif cmd == "hsend":
        message = " ".join(cmd_args) if cmd_args else ""
        return cmd_hsend(message)

    elif cmd == "hrecv":
        return cmd_hrecv(args.timeout)

    elif cmd == "chat":
        return cmd_chat()

    elif cmd == "wake":
        if not cmd_args:
            return {"error": "Usage: nclaude wake @peer [tmux|terminal|iterm|info]"}
        target = cmd_args[0]
        method = cmd_args[1] if len(cmd_args) > 1 else "auto"
        return cmd_wake(target, method)

    elif cmd == "sessions":
        return cmd_sessions()

    else:
        return {"error": f"Unknown command: {cmd}"}


def main() -> None:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    # Handle special flags
    if args.version:
        print(f"nclaude {__version__}")
        return

    if args.help or not args.command:
        show_help()
        return

    try:
        result = run_command(args)

        if result is not None:
            print(json.dumps(result, indent=2))

    except Exception as e:
        print(json.dumps({"error": str(e)}, indent=2))
        sys.exit(1)

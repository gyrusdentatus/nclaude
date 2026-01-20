"""CLI argument parsing and command dispatch for nclaude."""

import argparse
import json
import sys
from typing import Any, Dict, List, Optional

from . import __version__
from .config import create_config
from .rooms import get_room
from .utils.git import get_auto_session_id
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
)


def show_help() -> None:
    """Human-friendly help output."""
    help_text = """
nclaude - Claude-to-Claude Chat
===============================

QUICK START (3 terminals):
  Terminal 1 (human):  nclaude watch
  Terminal 2 (claude): nclaude send "hello" && nclaude check
  Terminal 3 (claude): nclaude check && nclaude send "hi back"

COMMANDS:
  send <msg>        Send message to all sessions
  check             Read all messages (pending + new)
  read              Read new messages only
  watch             Live message feed (like tail -f but pretty)
  status            Show chat status, sessions, and peers
  pending           Show messages from listen daemon
  listen            Start background message listener
  clear             Clear all messages
  whoami            Show current session ID
  pair <project>    Register peer for coordination
  unpair [project]  Remove peer (or all peers)
  peers             List current peers
  broadcast <msg>   Send BROADCAST from human to Claudes

FLAGS:
  --dir, -d NAME    Target different project (name or path)
  --type TYPE       Message type: MSG|TASK|REPLY|STATUS|URGENT|ERROR
  --timeout SECS    Timeout for watch command (0 = forever, default 60)
  --interval SECS   Polling interval for watch (default 1.0)
  --history N       Show last N lines before starting live feed
  --limit N         Max messages to return (for read command)
  --filter TYPE     Filter by type: TASK|REPLY|STATUS|URGENT|ERROR
  --all             Show all messages (not just new)
  --quiet, -q       Minimal output
  --global, -g      Use global room (~/.nclaude/)
  --to @NAME        Send to specific recipient
  --for-me          Only show messages addressed to me
  --all-peers       Broadcast to all registered peers

EXAMPLES:
  nclaude watch                           # live message feed
  nclaude watch --timeout 0               # watch forever
  nclaude watch --history 20              # show last 20 msgs then live
  nclaude watch --timeout 120 --interval 2
  nclaude send "Starting work on auth"
  nclaude send "Need review" --dir other-project
  nclaude read --dir /path/to/other/repo
  nclaude send "hello global" --global    # global room
  nclaude read --global                   # read from global room
  nclaude pair speaktojade-k8s            # register peer
  nclaude peers                           # list my peers
  nclaude unpair speaktojade-k8s          # remove specific peer
  nclaude send "CLAIMING: src/api.py" --type URGENT
  nclaude send "ACK: confirmed" --type REPLY
  nclaude check
  nclaude status
  nclaude broadcast "standup in 5" --all-peers  # to all peers
  nclaude broadcast "@main @feat-xyz review PR"  # to specific sessions
  nclaude broadcast "@all emergency alert"       # to everyone

PROTOCOL:
  SYN-ACK: Before parallel work, coordinate who does what
    A: nclaude send "SYN: I do X, you do Y. ACK?" --type TASK
    B: nclaude send "ACK: confirmed" --type REPLY

  CLAIMING: Before editing shared files
    nclaude send "CLAIMING: path/to/file" --type URGENT
    ... do work ...
    nclaude send "RELEASED: path/to/file" --type STATUS

LOG LOCATION:
  /tmp/nclaude/<repo-name>/messages.log
  ~/.nclaude/messages.log (global room)
"""
    print(help_text)


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="nclaude",
        description="Headless Claude-to-Claude messaging",
        add_help=False,
    )
    parser.add_argument(
        "-h", "--help", action="store_true", help="Show help message"
    )
    parser.add_argument(
        "-v", "--version", action="store_true", help="Show version"
    )
    parser.add_argument(
        "-d", "--dir", dest="dir", help="Target different project (name or path)"
    )
    parser.add_argument(
        "-g", "--global", dest="use_global", action="store_true",
        help="Use global room (~/.nclaude/)"
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
        help="Maximum messages to return (for read command)"
    )
    parser.add_argument(
        "--filter", dest="filter_type", default=None,
        help="Filter by message type: TASK|REPLY|STATUS|URGENT|ERROR"
    )
    parser.add_argument(
        "--to", dest="to_recipient", default=None,
        help="Send to specific recipient (@mention)"
    )
    parser.add_argument(
        "--for-me", dest="for_me", action="store_true",
        help="Only show messages addressed to me (or broadcast)"
    )
    parser.add_argument(
        "--storage", default="sqlite",
        help="Storage backend: sqlite|file (sqlite uses ~/.nclaude/messages.db)"
    )
    parser.add_argument(
        "--all-peers", dest="all_peers", action="store_true",
        help="Broadcast to all registered peers"
    )
    parser.add_argument(
        "command", nargs="?", help="Command to run"
    )
    parser.add_argument(
        "args", nargs="*", help="Command arguments"
    )

    return parser


def run_command(args: argparse.Namespace) -> Optional[Dict[str, Any]]:
    """Run a command based on parsed args.

    Args:
        args: Parsed command line arguments

    Returns:
        Dict result to print as JSON, or None for commands that handle output
    """
    cmd = args.command
    cmd_args = args.args or []

    # Get room and session
    room = get_room(
        use_global=args.use_global,
        dir_override=args.dir,
        storage_backend=args.storage,
    )
    session_id = get_auto_session_id()

    # Command dispatch
    if cmd == "init":
        room.storage.init()
        return {"status": "ok", "path": str(room.path)}

    elif cmd == "whoami":
        return cmd_whoami(room, session_id)

    elif cmd == "send":
        # Handle session_id in args for backwards compatibility
        if len(cmd_args) >= 2:
            # Explicit session_id provided
            session_id = cmd_args[0]
            message = " ".join(cmd_args[1:])
        elif len(cmd_args) == 1:
            message = cmd_args[0]
        else:
            message = ""

        return cmd_send(room, session_id, message, args.msg_type.upper(), to=args.to_recipient)

    elif cmd == "read":
        if cmd_args:
            session_id = cmd_args[0]
        return cmd_read(
            room, session_id, args.all, args.quiet,
            limit=args.limit, msg_type=args.filter_type
        )

    elif cmd == "status":
        return cmd_status(room)

    elif cmd == "clear":
        return cmd_clear(room)

    elif cmd == "pair":
        if not cmd_args:
            return {"error": "Usage: nclaude pair <project-name>"}
        return cmd_pair(room, session_id, cmd_args[0])

    elif cmd == "unpair":
        target = cmd_args[0] if cmd_args else None
        return cmd_unpair(room, target)

    elif cmd == "peers":
        return cmd_peers(room)

    elif cmd == "broadcast":
        message = " ".join(cmd_args) if cmd_args else ""
        return cmd_broadcast(room, message, all_peers=args.all_peers)

    elif cmd == "pending":
        if cmd_args:
            session_id = cmd_args[0]
        return cmd_pending(room, session_id)

    elif cmd == "check":
        if cmd_args:
            session_id = cmd_args[0]
        return cmd_check(room, session_id, for_me=args.for_me)

    elif cmd == "listen":
        if cmd_args:
            session_id = cmd_args[0]
        cmd_listen(room, session_id, int(args.interval))
        return None  # listen handles its own output

    elif cmd == "watch":
        cmd_watch(room, session_id, args.timeout, args.interval, args.history)
        return None  # watch handles its own output

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
        return cmd_chat(room)

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

        # In quiet mode, only print if there's something to say
        if result is not None:
            print(json.dumps(result, indent=2))

    except Exception as e:
        print(json.dumps({"error": str(e)}, indent=2))
        sys.exit(1)

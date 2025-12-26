#!/usr/bin/env python3
"""nclaude - headless Claude-to-Claude chat

A simple file-based message queue for communication between Claude Code sessions.
No sockets, no pipes, no bullshit.
"""
import fcntl
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def get_git_info():
    """Get git repo info for smart defaults"""
    try:
        # Get git common dir (works for worktrees too)
        git_common = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            capture_output=True, text=True, timeout=5
        )
        if git_common.returncode != 0:
            return None, None, None

        common_dir = Path(git_common.stdout.strip()).resolve()

        # Get repo root (for regular repos, parent of .git; for worktrees, the main worktree)
        repo_root = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5
        )
        repo_name = Path(repo_root.stdout.strip()).name if repo_root.returncode == 0 else "unknown"

        # Get current branch
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, timeout=5
        )
        branch_name = branch.stdout.strip() if branch.returncode == 0 else "detached"

        return common_dir, repo_name, branch_name
    except Exception:
        return None, None, None


def get_base_dir():
    """Get nclaude base directory, git-aware if possible"""
    # Explicit override always wins
    if "NCLAUDE_DIR" in os.environ:
        return Path(os.environ["NCLAUDE_DIR"])

    # Try git-aware path - use repo name for isolation (consistent across all sessions)
    _, repo_name, _ = get_git_info()
    if repo_name:
        # Use /tmp/nclaude/<repo-name>/ - same repo = same path, always
        return Path(f"/tmp/nclaude/{repo_name}")

    # Fallback for non-git directories
    return Path("/tmp/nclaude")


def get_auto_session_id():
    """Generate session ID from git context"""
    if "NCLAUDE_ID" in os.environ:
        return os.environ["NCLAUDE_ID"]

    _, repo_name, branch_name = get_git_info()
    if repo_name and branch_name:
        # Sanitize branch name (replace / with -)
        branch_safe = branch_name.replace("/", "-")
        return f"{repo_name}-{branch_safe}"

    return "claude"


# Initialize paths
BASE = get_base_dir()
LOG = BASE / "messages.log"
LOCK = BASE / ".lock"
SESSIONS = BASE / "sessions"
PENDING = BASE / "pending"


def init():
    """Initialize workspace"""
    SESSIONS.mkdir(parents=True, exist_ok=True)
    LOG.touch()
    LOCK.touch()
    return {"status": "ok", "path": str(BASE)}


def send(session_id: str, message: str, msg_type: str = "MSG"):
    """Send a message (atomic append with flock)

    Args:
        session_id: Session identifier
        message: Message content (can be multi-line)
        msg_type: Message type (MSG, TASK, REPLY, STATUS, ERROR, URGENT)
    """
    init()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    # Check if message is multi-line
    if "\n" in message:
        # Use delimited format for multi-line messages
        line = f"<<<[{ts}][{session_id}][{msg_type}]>>>\n{message}\n<<<END>>>\n"
    else:
        # Simple single-line format (backward compatible)
        if msg_type != "MSG":
            line = f"[{ts}] [{session_id}] [{msg_type}] {message}\n"
        else:
            line = f"[{ts}] [{session_id}] {message}\n"

    with open(LOCK, "r") as lock_fd:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        with open(LOG, "a") as f:
            f.write(line)
    return {"sent": message, "session": session_id, "timestamp": ts, "type": msg_type}


def read(session_id: str, all_messages: bool = False, quiet: bool = False):
    """Read new messages since last read

    Args:
        session_id: Session identifier
        all_messages: If True, read all messages, not just new ones
        quiet: If True, only output if there are new messages (for hooks)
    """
    init()
    pointer_file = SESSIONS / session_id

    # Get last read position
    last_line = 0
    if pointer_file.exists() and not all_messages:
        try:
            last_line = int(pointer_file.read_text().strip() or "0")
        except ValueError:
            last_line = 0

    # Read log
    if not LOG.exists():
        if quiet:
            return None  # Signal no output needed
        return {"messages": [], "new_count": 0, "total": 0}

    lines = LOG.read_text().splitlines()
    new_lines = lines[last_line:]

    # Update pointer
    pointer_file.write_text(str(len(lines)))

    # In quiet mode, only return if there are new messages
    if quiet and len(new_lines) == 0:
        return None

    return {
        "messages": new_lines,
        "new_count": len(new_lines),
        "total": len(lines)
    }


def status():
    """Get chat status"""
    if not BASE.exists() or not LOG.exists():
        return {"active": False, "message_count": 0, "sessions": [], "log_path": str(LOG)}

    lines = LOG.read_text().splitlines()
    sessions = []
    if SESSIONS.exists():
        sessions = [f.name for f in SESSIONS.iterdir() if f.is_file()]

    return {
        "active": True,
        "message_count": len(lines),
        "sessions": sessions,
        "log_path": str(LOG)
    }


def clear():
    """Clear all messages and session data"""
    if BASE.exists():
        shutil.rmtree(BASE)
    return {"status": "cleared"}


def pending(session_id: str):
    """Check for pending messages (written by listen daemon)

    The listen daemon writes line numbers to pending/<session_id> when new
    messages arrive. This function reads those line numbers, fetches the
    actual messages, and clears the pending file.
    """
    pending_file = PENDING / session_id

    if not pending_file.exists():
        return {"pending": False, "messages": [], "count": 0}

    # Read pending line range
    try:
        content = pending_file.read_text().strip()
        if not content:
            pending_file.unlink()
            return {"pending": False, "messages": [], "count": 0}

        # Format: "start_line:end_line" (0-indexed)
        start, end = map(int, content.split(":"))
    except (ValueError, FileNotFoundError):
        return {"pending": False, "messages": [], "count": 0}

    # Fetch messages from log
    if not LOG.exists():
        pending_file.unlink()
        return {"pending": False, "messages": [], "count": 0}

    lines = LOG.read_text().splitlines()
    pending_msgs = lines[start:end]

    # Clear pending file
    pending_file.unlink()

    # Update session pointer to current end
    pointer_file = SESSIONS / session_id
    pointer_file.parent.mkdir(parents=True, exist_ok=True)
    pointer_file.write_text(str(end))

    return {
        "pending": True,
        "messages": pending_msgs,
        "count": len(pending_msgs),
        "range": f"{start}:{end}"
    }


def listen(session_id: str, interval: int = 5):
    """Run daemon that monitors for new messages

    Runs in foreground - use & or nohup for background.
    Writes line range to pending/<session_id> when new messages arrive.
    Format: "start_line:end_line" (0-indexed, exclusive end)
    """
    init()
    PENDING.mkdir(parents=True, exist_ok=True)
    pending_file = PENDING / session_id
    pointer_file = SESSIONS / session_id

    # Handle graceful shutdown
    running = True
    def handle_signal(signum, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    print(json.dumps({
        "status": "listening",
        "session": session_id,
        "interval": interval,
        "pending_file": str(pending_file)
    }), flush=True)

    while running:
        try:
            # Get current pointer (last read position)
            last_read = 0
            if pointer_file.exists():
                try:
                    last_read = int(pointer_file.read_text().strip() or "0")
                except ValueError:
                    last_read = 0

            # Get total line count
            total_lines = 0
            if LOG.exists():
                total_lines = len(LOG.read_text().splitlines())

            # Check for new messages
            if total_lines > last_read:
                # Write pending range
                pending_file.write_text(f"{last_read}:{total_lines}")
                new_count = total_lines - last_read

                print(json.dumps({
                    "event": "new_messages",
                    "count": new_count,
                    "range": f"{last_read}:{total_lines}",
                    "session": session_id
                }), flush=True)

                # Terminal bell for human awareness
                print("\a", end="", flush=True)

            time.sleep(interval)
        except Exception as e:
            print(json.dumps({"error": str(e)}), file=sys.stderr, flush=True)
            time.sleep(interval)

    # Cleanup
    if pending_file.exists():
        pending_file.unlink()

    print(json.dumps({"status": "stopped", "session": session_id}), flush=True)


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: nclaude.py <init|send|read|status|clear|whoami|pending|listen> [args]"}))
        sys.exit(1)

    cmd = sys.argv[1]
    args = sys.argv[2:]

    # Parse flags
    quiet = "--quiet" in args or "-q" in args
    all_msgs = "--all" in args

    # Parse --type flag for send command
    msg_type = "MSG"
    for i, arg in enumerate(args):
        if arg == "--type" and i + 1 < len(args):
            msg_type = args[i + 1].upper()
            break

    # Get non-flag args (exclude flag values)
    skip_next = False
    positional = []
    for i, a in enumerate(args):
        if skip_next:
            skip_next = False
            continue
        if a in ("--type", "--interval"):
            skip_next = True
            continue
        if not a.startswith("-"):
            positional.append(a)

    try:
        if cmd == "init":
            result = init()
        elif cmd == "whoami":
            # Show auto-detected session info
            result = {
                "session_id": get_auto_session_id(),
                "base_dir": str(BASE),
                "log_path": str(LOG)
            }
        elif cmd == "send":
            # Use auto session ID if not provided
            if len(positional) >= 2:
                session_id = positional[0]
                message = " ".join(positional[1:])
            elif len(positional) == 1:
                session_id = get_auto_session_id()
                message = positional[0]
            else:
                session_id = get_auto_session_id()
                message = ""

            if not message:
                result = {"error": "No message provided"}
            else:
                result = send(session_id, message, msg_type)
        elif cmd == "read":
            session_id = positional[0] if positional else get_auto_session_id()
            result = read(session_id, all_msgs, quiet)
        elif cmd == "status":
            result = status()
        elif cmd == "clear":
            result = clear()
        elif cmd == "pending":
            session_id = positional[0] if positional else get_auto_session_id()
            result = pending(session_id)
        elif cmd == "listen":
            session_id = positional[0] if positional else get_auto_session_id()
            # Parse --interval flag
            interval = 5
            for i, arg in enumerate(args):
                if arg == "--interval" and i + 1 < len(args):
                    try:
                        interval = int(args[i + 1])
                    except ValueError:
                        pass
            listen(session_id, interval)
            result = None  # listen handles its own output
        else:
            result = {"error": f"Unknown command: {cmd}"}
    except Exception as e:
        result = {"error": str(e)}

    # In quiet mode, only print if there's something to say
    if result is not None:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

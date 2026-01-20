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
        # For worktrees, this points to main repo's .git dir
        git_common = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            capture_output=True, text=True, timeout=5
        )
        if git_common.returncode != 0:
            return None, None, None

        common_dir = Path(git_common.stdout.strip()).resolve()

        # Derive repo name from common_dir (works for both regular repos and worktrees)
        # common_dir is either:
        #   - /path/to/repo/.git (regular repo) -> repo name is parent.name
        #   - /path/to/repo/.git (from worktree) -> same, repo name is parent.name
        if common_dir.name == ".git":
            repo_name = common_dir.parent.name
        else:
            # Fallback to show-toplevel if common_dir structure is unexpected
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


# Initialize paths (can be overridden with --dir)
BASE = get_base_dir()
LOG = BASE / "messages.log"
LOCK = BASE / ".lock"
SESSIONS = BASE / "sessions"
PENDING = BASE / "pending"

# Global peers file (shared across all projects)
PEERS_FILE = Path("/tmp/nclaude/.peers")


def set_base_dir(path):
    """Override base directory (for cross-project messaging)"""
    global BASE, LOG, LOCK, SESSIONS, PENDING
    BASE = Path(path)
    LOG = BASE / "messages.log"
    LOCK = BASE / ".lock"
    SESSIONS = BASE / "sessions"
    PENDING = BASE / "pending"


def get_current_project():
    """Get current project name from BASE path"""
    return BASE.name


def load_peers():
    """Load peers from global peers file"""
    if not PEERS_FILE.exists():
        return {}
    try:
        return json.loads(PEERS_FILE.read_text())
    except (json.JSONDecodeError, IOError):
        return {}


def save_peers(peers):
    """Save peers to global peers file"""
    PEERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PEERS_FILE.write_text(json.dumps(peers, indent=2))


def pair(target_project):
    """Register a peer relationship"""
    current = get_current_project()
    peers = load_peers()

    # Add bidirectional pairing
    if current not in peers:
        peers[current] = []
    if target_project not in peers[current]:
        peers[current].append(target_project)

    if target_project not in peers:
        peers[target_project] = []
    if current not in peers[target_project]:
        peers[target_project].append(current)

    save_peers(peers)
    return {
        "status": "paired",
        "project": current,
        "peer": target_project,
        "all_peers": peers[current]
    }


def unpair(target_project=None):
    """Remove a peer relationship (or all if target is None)"""
    current = get_current_project()
    peers = load_peers()

    if target_project:
        # Remove specific peer
        if current in peers and target_project in peers[current]:
            peers[current].remove(target_project)
        if target_project in peers and current in peers[target_project]:
            peers[target_project].remove(current)
        save_peers(peers)
        return {"status": "unpaired", "project": current, "removed": target_project}
    else:
        # Remove all peers for current project
        removed = peers.pop(current, [])
        # Also remove current from other projects' peer lists
        for proj in peers:
            if current in peers[proj]:
                peers[proj].remove(current)
        save_peers(peers)
        return {"status": "unpaired_all", "project": current, "removed": removed}


def list_peers():
    """List all peers for current project"""
    current = get_current_project()
    peers = load_peers()
    my_peers = peers.get(current, [])
    return {
        "project": current,
        "peers": my_peers,
        "all_pairings": peers
    }


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
    current = get_current_project()
    peers = load_peers()
    my_peers = peers.get(current, [])

    if not BASE.exists() or not LOG.exists():
        return {
            "active": False,
            "project": current,
            "message_count": 0,
            "sessions": [],
            "peers": my_peers,
            "log_path": str(LOG)
        }

    lines = LOG.read_text().splitlines()
    sessions = []
    if SESSIONS.exists():
        sessions = [f.name for f in SESSIONS.iterdir() if f.is_file()]

    return {
        "active": True,
        "project": current,
        "message_count": len(lines),
        "sessions": sessions,
        "peers": my_peers,
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


def watch(timeout: int = 60, interval: float = 1.0, history: int = 0):
    """Watch messages live (like tail -f but formatted)

    Args:
        timeout: Max seconds to watch (0 = forever)
        interval: Polling interval in seconds
        history: Number of recent messages to show first (0 = none)
    """
    init()

    # Handle graceful shutdown
    running = True
    def handle_signal(signum, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # Get current line count to start from
    last_line = 0
    if LOG.exists():
        lines = LOG.read_text().splitlines()
        total_lines = len(lines)
        if history > 0 and total_lines > 0:
            # Show last N lines as history
            start_from = max(0, total_lines - history)
            last_line = start_from
        else:
            last_line = total_lines

    project = get_current_project()
    session_id = get_auto_session_id()

    print(f"\n{'='*60}")
    print(f"  ★ WATCHING: {project} (as {session_id})")
    print(f"  Timeout: {'forever' if timeout == 0 else f'{timeout}s'} | Interval: {interval}s")
    print(f"  Press Ctrl+C to stop")
    print(f"{'='*60}\n")

    start_time = time.time()

    while running:
        try:
            # Check timeout
            if timeout > 0 and (time.time() - start_time) >= timeout:
                print(f"\n[timeout reached after {timeout}s]")
                break

            # Read new lines
            if LOG.exists():
                lines = LOG.read_text().splitlines()
                new_lines = lines[last_line:]

                if new_lines:
                    for line in new_lines:
                        # Format the output nicely
                        if line.startswith("<<<["):
                            # Multi-line message header
                            print(f"\n\033[1;36m{line}\033[0m")  # Cyan bold
                        elif line == "<<<END>>>":
                            print(f"\033[1;36m{line}\033[0m")  # Cyan bold
                        elif line.startswith("["):
                            # Single-line message - parse and colorize
                            if "[URGENT]" in line or "[ERROR]" in line:
                                print(f"\033[1;31m{line}\033[0m")  # Red bold
                            elif "[BROADCAST]" in line or "[HUMAN]" in line:
                                print(f"\033[1;33m{line}\033[0m")  # Yellow bold
                            elif "[STATUS]" in line:
                                print(f"\033[1;32m{line}\033[0m")  # Green bold
                            elif "[TASK]" in line or "[REPLY]" in line:
                                print(f"\033[1;35m{line}\033[0m")  # Magenta bold
                            else:
                                print(line)
                        else:
                            # Message body content
                            print(f"  {line}")

                    last_line = len(lines)
                    # Terminal bell on new messages
                    print("\a", end="", flush=True)

            time.sleep(interval)
        except Exception as e:
            print(f"\033[1;31m[error: {e}]\033[0m", file=sys.stderr)
            time.sleep(interval)

    print(f"\n[stopped watching {project}]")
    return {"status": "stopped", "lines_seen": last_line}


def show_help():
    """Human-friendly help output"""
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

FLAGS:
  --dir, -d NAME    Target different project (name or path)
  --type TYPE       Message type: MSG|TASK|REPLY|STATUS|URGENT|ERROR
  --timeout SECS    Timeout for watch command (0 = forever, default 60)
  --interval SECS   Polling interval for watch (default 1.0)
  --history N       Show last N lines before starting live feed
  --all             Show all messages (not just new)
  --quiet, -q       Minimal output

EXAMPLES:
  nclaude watch                           # live message feed
  nclaude watch --timeout 0               # watch forever
  nclaude watch --history 20              # show last 20 msgs then live
  nclaude watch --timeout 120 --interval 2
  nclaude send "Starting work on auth"
  nclaude send "Need review" --dir other-project
  nclaude read --dir /path/to/other/repo
  nclaude pair speaktojade-k8s            # register peer
  nclaude peers                            # list my peers
  nclaude unpair speaktojade-k8s          # remove specific peer
  nclaude send "CLAIMING: src/api.py" --type URGENT
  nclaude send "ACK: confirmed" --type REPLY
  nclaude check
  nclaude status

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
"""
    print(help_text)


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        show_help()
        sys.exit(0)

    cmd = sys.argv[1]
    args = sys.argv[2:]

    # Parse --dir flag first (for cross-project messaging)
    for i, arg in enumerate(args):
        if arg in ("--dir", "-d") and i + 1 < len(args):
            target_dir = args[i + 1]
            # Resolve relative to /tmp/nclaude/ if just a name, otherwise use as path
            if "/" not in target_dir:
                set_base_dir(f"/tmp/nclaude/{target_dir}")
            else:
                # It's a path - get the git repo name from it
                try:
                    result = subprocess.run(
                        ["git", "-C", target_dir, "rev-parse", "--show-toplevel"],
                        capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0:
                        repo_name = Path(result.stdout.strip()).name
                        set_base_dir(f"/tmp/nclaude/{repo_name}")
                    else:
                        # Not a git repo, use directory name
                        set_base_dir(f"/tmp/nclaude/{Path(target_dir).name}")
                except Exception:
                    set_base_dir(f"/tmp/nclaude/{Path(target_dir).name}")
            break

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
        if a in ("--type", "--interval", "--dir", "-d"):
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
        elif cmd == "pair":
            if not positional:
                result = {"error": "Usage: nclaude pair <project-name>"}
            else:
                target = positional[0]
                current = get_current_project()  # Save before changing base
                result = pair(target)
                # Also send a PAIRED message to the target
                original_base = str(BASE)
                set_base_dir(f"/tmp/nclaude/{target}")
                send(get_auto_session_id(), f"PAIRED: {current} is now paired with you", "STATUS")
                set_base_dir(original_base)
        elif cmd == "unpair":
            target = positional[0] if positional else None
            result = unpair(target)
        elif cmd == "peers":
            result = list_peers()
        elif cmd == "broadcast":
            # Send a single message visible to all sessions
            message = " ".join(positional) if positional else ""
            if not message:
                result = {"error": "No message provided"}
            else:
                # Send as BROADCAST type from HUMAN sender
                result = send("HUMAN", message, "BROADCAST")
        elif cmd == "pending":
            session_id = positional[0] if positional else get_auto_session_id()
            result = pending(session_id)
        elif cmd == "check":
            # Combined pending + read - one-stop "catch me up" command
            session_id = positional[0] if positional else get_auto_session_id()
            pending_result = pending(session_id)
            read_result = read(session_id)
            result = {
                "pending_messages": pending_result.get("messages", []),
                "new_messages": read_result.get("messages", []),
                "pending_count": pending_result.get("count", 0),
                "new_count": read_result.get("new_count", 0),
                "total": pending_result.get("count", 0) + read_result.get("new_count", 0)
            }
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

        elif cmd == "watch":
            # Parse --timeout flag (default 60s)
            timeout = 60
            for i, arg in enumerate(args):
                if arg == "--timeout" and i + 1 < len(args):
                    try:
                        timeout = int(args[i + 1])
                    except ValueError:
                        pass
            # Parse --interval flag (default 1.0s)
            interval = 1.0
            for i, arg in enumerate(args):
                if arg == "--interval" and i + 1 < len(args):
                    try:
                        interval = float(args[i + 1])
                    except ValueError:
                        pass
            # Parse --history flag (default 0 = no history)
            history = 0
            for i, arg in enumerate(args):
                if arg == "--history" and i + 1 < len(args):
                    try:
                        history = int(args[i + 1])
                    except ValueError:
                        pass
            watch(timeout, interval, history)
            result = None  # watch handles its own output

        # Hub commands - delegate to hub.py and client.py
        elif cmd == "hub":
            import subprocess
            hub_script = Path(__file__).parent / "hub.py"
            subcmd = positional[0] if positional else "status"
            proc = subprocess.run(
                ["python3", str(hub_script), subcmd],
                capture_output=True, text=True
            )
            if proc.stdout:
                result = json.loads(proc.stdout)
            else:
                result = {"error": proc.stderr}

        elif cmd == "connect":
            import subprocess
            client_script = Path(__file__).parent / "client.py"
            session_id = positional[0] if positional else get_auto_session_id()
            proc = subprocess.run(
                ["python3", str(client_script), "connect", session_id],
                capture_output=True, text=True
            )
            if proc.stdout:
                result = json.loads(proc.stdout)
            else:
                result = {"error": proc.stderr}

        elif cmd == "hsend":  # hub send (real-time)
            import subprocess
            client_script = Path(__file__).parent / "client.py"
            message = " ".join(positional) if positional else ""
            if not message:
                result = {"error": "No message provided"}
            else:
                proc = subprocess.run(
                    ["python3", str(client_script), "send", message],
                    capture_output=True, text=True
                )
                if proc.stdout:
                    result = json.loads(proc.stdout)
                else:
                    result = {"error": proc.stderr}

        elif cmd == "hrecv":  # hub receive (real-time)
            import subprocess
            client_script = Path(__file__).parent / "client.py"
            timeout = "5"
            for i, arg in enumerate(args):
                if arg == "--timeout" and i + 1 < len(args):
                    timeout = args[i + 1]
            proc = subprocess.run(
                ["python3", str(client_script), "recv", "--timeout", timeout],
                capture_output=True, text=True
            )
            if proc.stdout:
                result = json.loads(proc.stdout)
            else:
                result = {"error": proc.stderr}

        elif cmd == "chat":
            # Interactive human chat mode
            init()
            print("\n" + "="*60)
            print("  ★★★ HUMAN CHAT MODE ★★★")
            print("  Messages will be marked [HUMAN] [BROADCAST]")
            print("  Type 'quit' or Ctrl+C to exit")
            print("="*60 + "\n")

            try:
                while True:
                    try:
                        msg = input("HUMAN> ")
                        if msg.lower() in ('quit', 'exit', 'q'):
                            print("Goodbye!")
                            break
                        if msg.strip():
                            result = send("HUMAN", msg, "BROADCAST")
                            print(f"  → Sent to all Claudes")
                    except EOFError:
                        break
            except KeyboardInterrupt:
                print("\nGoodbye!")
            result = None  # Don't print JSON at end

        else:
            result = {"error": f"Unknown command: {cmd}"}
    except Exception as e:
        result = {"error": str(e)}

    # In quiet mode, only print if there's something to say
    if result is not None:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

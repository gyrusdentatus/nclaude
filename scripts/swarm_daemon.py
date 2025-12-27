#!/usr/bin/env python3
"""
Swarm Daemon - Claude-to-Claude coordination via spawn + resume

Unlike injection approaches that try to send input to running interactive sessions,
this daemon uses the opcode-proven approach:
1. Track session IDs from spawned Claudes
2. When new message arrives, spawn `claude --resume <session_id> -p "check messages"`
3. Claude resumes with full context and handles the message

Usage:
    python3 swarm_daemon.py register <session_name> <session_id>  # Register a session
    python3 swarm_daemon.py spawn <session_name> <prompt>          # Spawn new Claude
    python3 swarm_daemon.py resume <session_name> <prompt>         # Resume existing
    python3 swarm_daemon.py notify <session_name>                  # Resume to check messages
    python3 swarm_daemon.py watch                                  # Daemon mode
    python3 swarm_daemon.py list                                   # List sessions
    python3 swarm_daemon.py swarm <n> <task>                       # Spawn N Claudes to divide work
    python3 swarm_daemon.py ask <session_name> <question>          # Ask and show answer
    python3 swarm_daemon.py logs                                   # Watch logs (current repo only)
    python3 swarm_daemon.py logs --all                             # Watch all repo logs
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Configuration
CLAUDE_BINARY = os.path.expanduser("~/.claude/local/node_modules/.bin/claude")
NCLAUDE_DIR = Path(os.environ.get("NCLAUDE_DIR", "/tmp/nclaude"))

# ANSI colors for swarm agents
COLORS = {
    'swarm-1': '\033[94m',   # Blue
    'swarm-2': '\033[92m',   # Green
    'swarm-3': '\033[93m',   # Yellow
    'swarm-4': '\033[95m',   # Magenta
    'swarm-5': '\033[96m',   # Cyan
    'swarm-6': '\033[91m',   # Red
    'swarm-7': '\033[97m',   # White
    'swarm-8': '\033[90m',   # Gray
    'reset': '\033[0m',
    'bold': '\033[1m',
    'dim': '\033[2m',
}

def colorize(session: str, text: str) -> str:
    """Add color to text based on session name"""
    color = COLORS.get(session, '')
    reset = COLORS['reset']
    if color:
        return f"{color}{text}{reset}"
    # Try to match swarm-N pattern
    if session.startswith('swarm-'):
        try:
            n = int(session.split('-')[1]) % 8 + 1
            color = COLORS.get(f'swarm-{n}', '')
            return f"{color}{text}{reset}"
        except (ValueError, IndexError):
            pass
    return text


def get_nclaude_dir() -> Path:
    """Get git-aware nclaude directory"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            repo_name = Path(result.stdout.strip()).name
            return Path(f"/tmp/nclaude/{repo_name}")
    except Exception:
        pass
    return NCLAUDE_DIR


def get_registry_path() -> Path:
    """Get path to session registry"""
    nclaude_dir = get_nclaude_dir()
    nclaude_dir.mkdir(parents=True, exist_ok=True)
    return nclaude_dir / "sessions.json"


def get_log_path() -> Path:
    """Get path to messages.log"""
    return get_nclaude_dir() / "messages.log"


def load_registry() -> dict:
    """Load session registry"""
    path = get_registry_path()
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return {"sessions": {}, "last_line": 0}


def save_registry(registry: dict):
    """Save session registry"""
    path = get_registry_path()
    path.write_text(json.dumps(registry, indent=2))


def register_session(session_name: str, session_id: str):
    """Register a session ID for a session name"""
    registry = load_registry()
    registry["sessions"][session_name] = {
        "session_id": session_id,
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "last_resumed": None
    }
    save_registry(registry)
    print(json.dumps({
        "registered": session_name,
        "session_id": session_id
    }))


def spawn_claude(session_name: str, prompt: str, timeout: int = 120) -> dict:
    """
    Spawn a new Claude session with -p flag.
    Returns session info including the session_id for later resume.
    """
    cmd = [
        CLAUDE_BINARY,
        "-p", prompt,
        "--output-format", "stream-json",
        "--dangerously-skip-permissions",
        "--verbose"
    ]

    env = os.environ.copy()
    env["NCLAUDE_ID"] = session_name

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=os.getcwd(),
            env=env
        )

        # Parse JSONL output to find session ID and response text
        session_id = None
        response_parts = []
        for line in result.stdout.splitlines():
            try:
                data = json.loads(line)
                if "session_id" in data:
                    session_id = data["session_id"]
                # Extract assistant message content
                if data.get("type") == "assistant" and "message" in data:
                    msg = data["message"]
                    if "content" in msg:
                        for block in msg["content"]:
                            if block.get("type") == "text":
                                response_parts.append(block.get("text", ""))
            except Exception:
                continue

        if session_id:
            # Auto-register the session
            register_session(session_name, session_id)

        return {
            "session_name": session_name,
            "session_id": session_id,
            "returncode": result.returncode,
            "success": result.returncode == 0 and session_id is not None,
            "response": "\n".join(response_parts) if response_parts else None
        }

    except subprocess.TimeoutExpired:
        return {"session_name": session_name, "error": "timeout", "success": False}
    except Exception as e:
        return {"session_name": session_name, "error": str(e), "success": False}


def resume_claude(session_name: str, prompt: str, timeout: int = 120) -> dict:
    """
    Resume an existing Claude session using --resume flag.
    Looks up session_id from registry.
    """
    registry = load_registry()

    if session_name not in registry["sessions"]:
        return {"error": f"Session {session_name} not registered", "success": False}

    session_id = registry["sessions"][session_name]["session_id"]

    cmd = [
        CLAUDE_BINARY,
        "--resume", session_id,
        "-p", prompt,
        "--output-format", "stream-json",
        "--dangerously-skip-permissions"
    ]

    env = os.environ.copy()
    env["NCLAUDE_ID"] = session_name

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=os.getcwd(),
            env=env
        )

        # Update last_resumed
        registry["sessions"][session_name]["last_resumed"] = datetime.now(timezone.utc).isoformat()
        save_registry(registry)

        return {
            "session_name": session_name,
            "session_id": session_id,
            "returncode": result.returncode,
            "success": result.returncode == 0
        }

    except subprocess.TimeoutExpired:
        return {"session_name": session_name, "error": "timeout", "success": False}
    except Exception as e:
        return {"session_name": session_name, "error": str(e), "success": False}


def notify_session(session_name: str) -> dict:
    """
    Resume a session to check nclaude messages.
    This is the core "push notification" - spawn claude --resume with "check messages" prompt.
    """
    return resume_claude(
        session_name,
        "You have new nclaude messages. Run: python3 scripts/nclaude.py read. Report what you find and take appropriate action."
    )


def list_sessions():
    """List all registered sessions"""
    registry = load_registry()
    print(json.dumps(registry["sessions"], indent=2))


def ask_claude(session_name: str, question: str, timeout: int = 120) -> str:
    """
    Spawn Claude with a question and return the actual answer text.
    Useful for humans to see what Claude responds.
    """
    cmd = [
        CLAUDE_BINARY,
        "-p", question,
        "--output-format", "stream-json",
        "--dangerously-skip-permissions"
    ]

    env = os.environ.copy()
    env["NCLAUDE_ID"] = session_name

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=os.getcwd(),
            env=env
        )

        # Parse JSONL to extract assistant message content
        answer_parts = []
        session_id = None
        for line in result.stdout.splitlines():
            try:
                data = json.loads(line)
                if "session_id" in data:
                    session_id = data["session_id"]
                # Look for assistant message content
                if data.get("type") == "assistant" and "message" in data:
                    msg = data["message"]
                    if "content" in msg:
                        for block in msg["content"]:
                            if block.get("type") == "text":
                                answer_parts.append(block.get("text", ""))
            except Exception:
                continue

        if session_id:
            register_session(session_name, session_id)

        return "\n".join(answer_parts) if answer_parts else "(no text response)"

    except subprocess.TimeoutExpired:
        return "(timeout)"
    except Exception as e:
        return f"(error: {e})"


def swarm_spawn(n: int, task: str, timeout: int = 180):
    """
    Spawn N Claudes to divide work on a task.
    Each Claude gets assigned a portion of the work.
    """
    import concurrent.futures

    print(f"Spawning {n} Claudes to work on: {task[:60]}...")
    print("-" * 60)

    def spawn_worker(i: int) -> dict:
        agent_name = f"swarm-{i}"
        prompt = f"""You are swarm agent {i} of {n}.

TASK TO DIVIDE: {task}

Your job is to handle part {i}/{n} of this task. Coordinate via nclaude:
- First check messages: python3 scripts/nclaude.py read
- Claim your portion: python3 scripts/nclaude.py send "CLAIMING part {i}/{n}: <what you're doing>"
- When done: python3 scripts/nclaude.py send "DONE part {i}/{n}: <result>"

Be concise. Focus on your portion only."""

        result = spawn_claude(agent_name, prompt, timeout=timeout)
        return {"agent": agent_name, **result}

    # Spawn all in parallel
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=n) as executor:
        futures = [executor.submit(spawn_worker, i) for i in range(1, n + 1)]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            agent = result['agent']
            status = f"{COLORS['bold']}OK{COLORS['reset']}" if result.get('success') else f"{COLORS['bold']}\033[91mFAILED{COLORS['reset']}"
            print(f"  {colorize(agent, agent)}: {status}")

            # Show response preview (first 200 chars)
            if result.get('response'):
                preview = result['response'][:200].replace('\n', ' ')
                if len(result['response']) > 200:
                    preview += "..."
                print(f"    {COLORS['dim']}{preview}{COLORS['reset']}")

            results.append(result)

    print("-" * 60)
    print(f"Spawned {sum(1 for r in results if r.get('success'))}/{n} agents successfully")
    print(f"\n{COLORS['dim']}To see their work:{COLORS['reset']} python3 scripts/swarm_daemon.py logs")
    print(f"{COLORS['dim']}To resume an agent:{COLORS['reset']} python3 scripts/swarm_daemon.py resume swarm-1 'continue'")

    return results


def watch_daemon(interval: int = 5):
    """
    Daemon mode: monitor messages.log and trigger resumes for relevant sessions.

    When a new message arrives for session X, we resume session X to check messages.
    """
    print(json.dumps({
        "status": "starting",
        "log_path": str(get_log_path()),
        "interval": interval
    }))

    registry = load_registry()
    log_path = get_log_path()

    # Track last line we've seen
    last_line = registry.get("last_line", 0)
    if log_path.exists():
        current_lines = len(log_path.read_text().splitlines())
        if last_line > current_lines:
            # Log was truncated/cleared
            last_line = 0
        elif last_line == 0:
            # Start from current position (don't process old messages)
            last_line = current_lines

    notified_this_round = set()

    while True:
        try:
            if not log_path.exists():
                time.sleep(interval)
                continue

            lines = log_path.read_text().splitlines()
            new_lines = lines[last_line:]
            last_line = len(lines)

            # Save position
            registry = load_registry()
            registry["last_line"] = last_line
            save_registry(registry)

            if new_lines:
                # Parse new messages to find target sessions
                import re
                for line in new_lines:
                    # Extract sender from message format
                    # [timestamp] [session_id] message
                    # or <<<[ts][session_id][type]>>>
                    match = re.search(r'\[(\w+(?:-\w+)*)\]', line)
                    if match:
                        sender = match.group(1)

                        # Notify all OTHER registered sessions
                        for session_name in registry["sessions"]:
                            if session_name != sender and session_name not in notified_this_round:
                                print(json.dumps({
                                    "event": "new_message",
                                    "from": sender,
                                    "notifying": session_name
                                }))

                                result = notify_session(session_name)
                                print(json.dumps({
                                    "event": "notified",
                                    "session": session_name,
                                    "result": result
                                }))
                                notified_this_round.add(session_name)

                # Clear notified set after processing all new messages
                notified_this_round.clear()

            time.sleep(interval)

        except KeyboardInterrupt:
            print(json.dumps({"status": "stopped"}))
            break
        except Exception as e:
            print(json.dumps({"error": str(e)}), file=sys.stderr)
            time.sleep(interval)


def watch_logs(all_repos: bool = False):
    """
    Watch message logs with colored output.
    By default only watches current repo's log.
    """
    import re
    import select

    if all_repos:
        log_pattern = "/tmp/nclaude/*/messages.log"
        print(f"{COLORS['bold']}Watching ALL repo logs: {log_pattern}{COLORS['reset']}")
    else:
        log_path = get_log_path()
        log_pattern = str(log_path)
        print(f"{COLORS['bold']}Watching: {log_pattern}{COLORS['reset']}")

    print(f"{COLORS['dim']}Press Ctrl+C to stop{COLORS['reset']}\n")

    # Use tail -f with subprocess
    cmd = ["tail", "-f"] + (["-q"] if all_repos else [])
    if all_repos:
        import glob
        files = glob.glob("/tmp/nclaude/*/messages.log")
        if not files:
            print("No log files found")
            return
        cmd.extend(files)
    else:
        if not Path(log_pattern).exists():
            print(f"Log file not found: {log_pattern}")
            print("Start a Claude session first to create the log.")
            return
        cmd.append(log_pattern)

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        while True:
            # Read line by line
            line = proc.stdout.readline()
            if not line:
                break

            # Parse and colorize
            # Format: [timestamp] [session] message or <<<[ts][session][type]>>>
            match = re.search(r'\[(\w+(?:-\w+)*)\]', line)
            if match:
                session = match.group(1)
                # Skip timestamps that look like ISO format
                if not re.match(r'\d{4}-\d{2}-\d{2}', session):
                    print(colorize(session, line.rstrip()))
                    continue
            print(line.rstrip())

    except KeyboardInterrupt:
        print(f"\n{COLORS['dim']}Stopped watching logs{COLORS['reset']}")
        proc.terminate()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "register":
        if len(sys.argv) < 4:
            print("Usage: swarm_daemon.py register <session_name> <session_id>")
            sys.exit(1)
        register_session(sys.argv[2], sys.argv[3])

    elif cmd == "spawn":
        if len(sys.argv) < 4:
            print("Usage: swarm_daemon.py spawn <session_name> <prompt>")
            sys.exit(1)
        result = spawn_claude(sys.argv[2], " ".join(sys.argv[3:]))
        print(json.dumps(result, indent=2))

    elif cmd == "resume":
        if len(sys.argv) < 4:
            print("Usage: swarm_daemon.py resume <session_name> <prompt>")
            sys.exit(1)
        result = resume_claude(sys.argv[2], " ".join(sys.argv[3:]))
        print(json.dumps(result, indent=2))

    elif cmd == "notify":
        if len(sys.argv) < 3:
            print("Usage: swarm_daemon.py notify <session_name>")
            sys.exit(1)
        result = notify_session(sys.argv[2])
        print(json.dumps(result, indent=2))

    elif cmd == "list":
        list_sessions()

    elif cmd == "watch":
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        watch_daemon(interval)

    elif cmd == "swarm":
        if len(sys.argv) < 4:
            print("Usage: swarm_daemon.py swarm <n> <task description>")
            print("Example: swarm_daemon.py swarm 4 'Review all Python files in src/'")
            sys.exit(1)
        n = int(sys.argv[2])
        task = " ".join(sys.argv[3:])
        swarm_spawn(n, task)

    elif cmd == "ask":
        if len(sys.argv) < 4:
            print("Usage: swarm_daemon.py ask <session_name> <question>")
            print("Example: swarm_daemon.py ask test 'What is 2+2?'")
            sys.exit(1)
        answer = ask_claude(sys.argv[2], " ".join(sys.argv[3:]))
        print(f"\n{'='*60}")
        print(f"Answer from {sys.argv[2]}:")
        print(f"{'='*60}")
        print(answer)

    elif cmd == "logs":
        all_repos = "--all" in sys.argv
        watch_logs(all_repos=all_repos)

    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()

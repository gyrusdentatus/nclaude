#!/usr/bin/env python3
"""nclaude injector - Push notifications via TTY injection

Monitors messages.log and injects 'check logs' into idle Claude sessions.
Works with iTerm (osascript) or tmux (send-keys).
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path


def get_claude_sessions():
    """Get mapping of session_id -> tty for running Claude processes"""
    sessions = {}
    seen_ttys = set()

    try:
        # First pass: find claude processes with NCLAUDE_ID in their child processes
        result = subprocess.run(
            ['ps', 'eww', '-o', 'pid,tty,command'],
            capture_output=True, text=True, timeout=5
        )

        for line in result.stdout.splitlines():
            # Look for NCLAUDE_ID in environment
            match = re.search(r'NCLAUDE_ID=(\S+)', line)
            if match:
                session_id = match.group(1)
                parts = line.split()
                if len(parts) >= 2:
                    pid = parts[0]
                    tty = parts[1]
                    if tty and tty not in ('??', '?'):
                        if tty not in seen_ttys:
                            sessions[session_id] = {
                                'pid': pid,
                                'tty': tty,
                                'tty_path': f'/dev/{tty}'
                            }
                            seen_ttys.add(tty)

        # Second pass: find ALL claude CLI processes (the main "claude" command)
        # These may not have NCLAUDE_ID visible but are still Claude sessions
        result = subprocess.run(
            ['ps', '-o', 'pid,tty,command'],
            capture_output=True, text=True, timeout=5
        )

        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 3:
                pid = parts[0]
                tty = parts[1]
                cmd = parts[2]

                # Match the main claude process (not child MCP servers, etc)
                # The main process is just "claude" without path components
                if cmd == 'claude' and tty not in ('??', '?', 'TT'):
                    if tty not in seen_ttys:
                        # Use tty as session ID
                        session_id = f"claude-{tty}"
                        sessions[session_id] = {
                            'pid': pid,
                            'tty': tty,
                            'tty_path': f'/dev/{tty}'
                        }
                        seen_ttys.add(tty)

    except Exception as e:
        print(f"Error getting sessions: {e}", file=sys.stderr)

    return sessions


def inject_iterm(tty: str, message: str) -> bool:
    """Inject message into iTerm session via osascript"""
    script = f'''
    tell application "iTerm"
        repeat with w in windows
            repeat with t in tabs of w
                repeat with s in sessions of t
                    set sessionTTY to tty of s
                    if sessionTTY contains "{tty}" then
                        tell s
                            -- write text with explicit newline character
                            write text "{message}" & return
                        end tell
                        return true
                    end if
                end repeat
            end repeat
        end repeat
        return false
    end tell
    '''

    try:
        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True, text=True, timeout=5
        )
        return 'true' in result.stdout.lower()
    except Exception as e:
        print(f"osascript failed: {e}", file=sys.stderr)
        return False


def inject_tmux(session_name: str, message: str) -> bool:
    """Inject message into tmux session via send-keys"""
    try:
        subprocess.run(
            ['tmux', 'send-keys', '-t', session_name, message, 'Enter'],
            capture_output=True, timeout=5
        )
        return True
    except Exception:
        return False


def get_message_log_path():
    """Get the nclaude message log path"""
    # Try git-aware path
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--show-toplevel'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            repo_name = Path(result.stdout.strip()).name
            return Path(f'/tmp/nclaude/{repo_name}/messages.log')
    except Exception:
        pass

    return Path('/tmp/nclaude/messages.log')


def monitor_and_inject(interval: int = 2):
    """Main loop: monitor messages and inject notifications"""
    log_path = get_message_log_path()
    print(json.dumps({
        "status": "starting",
        "log_path": str(log_path),
        "interval": interval
    }))

    last_line_count = 0
    if log_path.exists():
        last_line_count = len(log_path.read_text().splitlines())

    # Track which sessions have pending notifications
    notified = set()

    while True:
        try:
            # Get current Claude sessions
            sessions = get_claude_sessions()

            if not log_path.exists():
                time.sleep(interval)
                continue

            lines = log_path.read_text().splitlines()
            new_lines = lines[last_line_count:]
            last_line_count = len(lines)

            if new_lines:
                # Parse new messages and find target sessions
                for line in new_lines:
                    # Extract session from message
                    # Format: [timestamp] [session] message
                    # or: <<<[ts][session][type]>>>
                    match = re.search(r'\[(\w+(?:-\w+)*)\]', line)
                    if match:
                        sender = match.group(1)

                        # Notify all OTHER sessions about new message
                        for session_id, info in sessions.items():
                            if session_id != sender and session_id not in notified:
                                tty = info['tty']

                                # Try iTerm injection
                                if inject_iterm(tty, '# New nclaude message - check logs'):
                                    print(json.dumps({
                                        "event": "injected",
                                        "session": session_id,
                                        "tty": tty,
                                        "method": "iterm"
                                    }))
                                    notified.add(session_id)
                                else:
                                    # Try tmux fallback
                                    if inject_tmux(session_id, '# New nclaude message'):
                                        print(json.dumps({
                                            "event": "injected",
                                            "session": session_id,
                                            "method": "tmux"
                                        }))
                                        notified.add(session_id)

                # Clear notified set after a delay
                notified.clear()

            time.sleep(interval)

        except KeyboardInterrupt:
            print(json.dumps({"status": "stopped"}))
            break
        except Exception as e:
            print(json.dumps({"error": str(e)}), file=sys.stderr)
            time.sleep(interval)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='nclaude injector daemon')
    parser.add_argument('command', choices=['start', 'test', 'sessions'],
                        help='Command to run')
    parser.add_argument('--interval', type=int, default=2,
                        help='Poll interval in seconds')
    parser.add_argument('--tty', help='TTY to test injection on')

    args = parser.parse_args()

    if args.command == 'sessions':
        sessions = get_claude_sessions()
        print(json.dumps(sessions, indent=2))

    elif args.command == 'test':
        if not args.tty:
            print("Error: --tty required for test", file=sys.stderr)
            sys.exit(1)

        success = inject_iterm(args.tty, '# TEST INJECTION')
        print(json.dumps({"success": success, "tty": args.tty}))

    elif args.command == 'start':
        monitor_and_inject(args.interval)


if __name__ == '__main__':
    main()

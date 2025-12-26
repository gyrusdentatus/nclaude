# NCLAUDE - Claude-to-Claude Chat

Headless message passing between Claude Code sessions. No sockets, no pipes, no bullshit.

## Quick Start

```bash
# Session A
export NCLAUDE_ID="claude-a"
/nclaude:send "Starting work on X"

# Session B
export NCLAUDE_ID="claude-b"
/nclaude:read
/nclaude:send "Acknowledged, working on Y"
```

## Commands

| Command | Description |
|---------|-------------|
| `/nclaude:send <msg>` | Send a message |
| `/nclaude:read` | Read new messages |
| `/nclaude:status` | Show chat status |
| `/nclaude:clear` | Clear all messages |
| `/nclaude:watch` | Instructions for human monitoring |

## Direct Usage (without slash commands)

```bash
python3 scripts/nclaude.py send "session-id" "Your message"
python3 scripts/nclaude.py read "session-id"
python3 scripts/nclaude.py read "session-id" --all  # Include already-read
python3 scripts/nclaude.py status
python3 scripts/nclaude.py clear
```

## Human Monitoring

Watch messages live in a separate terminal:
```bash
tail -f /tmp/nclaude/messages.log
```

## Message Format

```
[2025-12-26T14:30:00] [claude-a] Starting work on X
[2025-12-26T14:30:05] [claude-b] Acknowledged, working on Y
```

## Data Location

- Messages: `/tmp/nclaude/messages.log`
- Session pointers: `/tmp/nclaude/sessions/<session-id>`
- Override with: `NCLAUDE_DIR=/custom/path`

## How It Works

1. Messages append to a shared log file (atomic via flock)
2. Each session tracks its last-read line number
3. `/nclaude:read` returns only unread messages
4. No sockets, no pipes, no blocking - just files

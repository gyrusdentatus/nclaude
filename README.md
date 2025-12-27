# nclaude

Claude-to-Claude chat. No sockets, no pipes, no bullshit.

## Watch Claudes Talk (30 seconds)

```bash
# Terminal 1: Watch the conversation
tail -f /tmp/nclaude/$(basename $(pwd))/messages.log

# Terminal 2: Start Claude
claude
# then: /send "Hello from Claude A"

# Terminal 3: Another Claude
claude
# then: /check
# then: /send "Hello back from Claude B"
```

That's it. Two Claudes chatting, you watching.

---

## Two Modes

### Casual Mode (2-3 Claudes)

Best for: pair programming, code review, brainstorming

```bash
# Human watches
tail -f /tmp/nclaude/*/messages.log

# Each Claude session uses slash commands
/send "Starting work on auth module"      # Send message
/check                                     # Read messages from others
/send "Done with auth" --type STATUS       # Send with type
```

Zero setup. Just open terminals and chat.

### Power Mode (Swarm)

Best for: parallel tasks, code review, bulk operations

```bash
# Spawn 4 Claudes to divide work
python3 scripts/swarm_daemon.py swarm 4 "Review all Python files in scripts/"

# Ask a quick question
python3 scripts/swarm_daemon.py ask test "How to check file inode in bash?"

# Watch their work
tail -f /tmp/nclaude/*/messages.log
```

Claudes spawn, divide work, report findings.

---

## Install

```bash
git clone https://github.com/gyrusdentatus/nclaude.git
cd nclaude

# Optional: Install as Claude Code plugin
claude plugin install ./nclaude --scope project
```

No dependencies. Pure Python stdlib.

---

## Slash Commands

| Command | Description |
|---------|-------------|
| `/send <msg>` | Send message to all |
| `/read` | Read new messages |
| `/check` | Sync (pending + read) |
| `/status` | Show chat status |
| `/clear` | Clear messages |

Message types: `--type MSG|TASK|REPLY|STATUS|ERROR|URGENT`

---

## Swarm Daemon Commands

```bash
python3 scripts/swarm_daemon.py <command>

spawn <name> <prompt>    # Spawn single Claude
resume <name> <prompt>   # Resume existing session
ask <name> <question>    # Ask and show answer
swarm <n> <task>         # Spawn N Claudes for task
list                     # Show registered sessions
watch                    # Auto-resume on new messages
```

---

## How It Works

```
┌─────────────┐     ┌─────────────┐
│  Claude A   │     │  Claude B   │
│   /send     │────▶│   /check    │
└─────────────┘     └─────────────┘
       │                   │
       ▼                   ▼
┌─────────────────────────────────┐
│  /tmp/nclaude/repo/messages.log │
│  (atomic writes via flock)      │
└─────────────────────────────────┘
       │
       ▼
┌─────────────┐
│   Human     │
│  tail -f    │
└─────────────┘
```

- Messages append to shared log (atomic via `flock`)
- Each session tracks last-read line
- Git-aware: same repo = same log (including worktrees)

---

## Claude-to-Claude Protocol

### SYN-ACK Handshake

```bash
# Claude A proposes
/send "SYN: I'll do auth, you do tests. ACK?" --type TASK

# Claude B confirms
/send "ACK: Confirmed, starting tests" --type REPLY
```

### File Claiming

```bash
# Before editing
/send "CLAIMING: src/auth.py" --type URGENT

# After done
/send "RELEASED: src/auth.py" --type STATUS
```

### Message Types

- `MSG` - General message (default)
- `TASK` - Work assignment
- `REPLY` - Response
- `STATUS` - Progress update
- `URGENT` - Priority/conflicts
- `ERROR` - Problems

---

## Hub Mode (Real-Time)

Unix socket server for instant @mention routing:

```bash
# Start hub
python3 scripts/hub.py start &

# Connect and send
python3 scripts/client.py connect claude-a
python3 scripts/client.py send "@claude-b review this PR"

# Other session receives instantly
python3 scripts/client.py recv
```

See [Hub Documentation](docs/hub.md) for details.

---

## Limitations

- **No push** - Claude can't wake from idle. User must trigger `/check`
- **Polling burns tokens** - Use SYN-ACK, don't spin-loop
- **Async only** - Message passing, not real-time chat

---

## License

MIT

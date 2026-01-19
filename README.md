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

### One-Command Setup (tmux)

```bash
# Launch everything in one tmux session
nclaude-tmux

# With preset config (auto-starts claude with prompts)
nclaude-tmux -c gcp-k8s

# Custom prompts
nclaude-tmux -a "Deploy API" -b "Monitor and rollback if errors"
```

Creates:
```
┌─────────────┬─────────────┐
│  Claude A   │  Claude B   │
│  (claude)   │  (claude)   │
├─────────────┴─────────────┤
│      Message Logs         │
└───────────────────────────┘
```

**Preset Configs:**

| Config | Claude A | Claude B |
|--------|----------|----------|
| `gcp-k8s` | Terragrunt, GKE, IAM, networking | DNS, certs, ingress, monitoring |
| `review` | Code author/defender | Code reviewer/critic |
| `test` | Implement features | Write tests |

```bash
nclaude-tmux -c gcp-k8s    # GCP/GKE infrastructure
nclaude-tmux -c review     # Code review
nclaude-tmux -c test       # TDD pair
```

All presets include SYN-ACK coordination and file claiming protocols.

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
swarm swarm 4 "Review all Python files in scripts/"

# Ask a quick question
swarm ask test "How to check file inode in bash?"

# Watch their work
swarm logs
```

Claudes spawn, divide work, report findings.

---

## Install

```bash
git clone https://github.com/SpeakToJade/nclaude.git
cd nclaude

# Install globally (recommended)
uv tool install .

# Symlink slash commands for global use
for f in .claude/commands/n*.md; do
  ln -sf "$(pwd)/$f" ~/.claude/commands/
done

# Now available anywhere:
nclaude check
swarm list
```

No dependencies. Pure Python stdlib.

---

## Permissions

Allow Claude to run nclaude commands without prompting:

**Global (~/.claude/settings.json):**
```json
{
  "permissions": {
    "allow": [
      "Bash(nclaude *)"
    ]
  }
}
```

**Project (.claude/settings.json in repo root):**
```json
{
  "permissions": {
    "allow": [
      "Bash(nclaude *)"
    ]
  }
}
```

**Local (.claude/settings.local.json - not committed):**
```json
{
  "permissions": {
    "allow": [
      "Bash(nclaude *)"
    ]
  }
}
```

Priority: local > project > global

---

## Slash Commands

| Command | Description |
|---------|-------------|
| `/nsend <msg>` | Send message to all |
| `/nread` | Read new messages |
| `/ncheck` | Sync (pending + read) |
| `/nstatus` | Show chat status and peers |
| `/nclear` | Clear messages |
| `/npair <project>` | Pair with another Claude session |

**Cross-project messaging:**
```bash
/nsend "Hey, need review" --dir other-project
/nread --dir /path/to/other/repo
```

**Peer commands:**
```bash
nclaude pair speaktojade-k8s    # Register peer
nclaude peers                    # List peers
nclaude unpair speaktojade-k8s  # Remove peer
```

Message types: `--type MSG|TASK|REPLY|STATUS|ERROR|URGENT`

---

## Swarm Daemon Commands

```bash
swarm <command>

spawn <name> <prompt>    # Spawn single Claude
resume <name> <prompt>   # Resume existing session
ask <name> <question>    # Ask and show answer
swarm <n> <task>         # Spawn N Claudes for task
list                     # Show registered sessions
logs                     # Watch logs with colors
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

## Troubleshooting

**Messages not showing?**
```bash
# Check the log path
nclaude whoami
# Verify file exists
ls -la /tmp/nclaude/$(basename $(pwd))/messages.log
```

**Wrong repo/session?**
```bash
# Override session ID
export NCLAUDE_ID="my-custom-id"
# Or override entire directory
export NCLAUDE_DIR="/tmp/nclaude/shared"
```

**Claudes not seeing each other?**
```bash
# All sessions must be in same repo (or use same NCLAUDE_DIR)
# Worktrees share automatically (same git common dir)
git rev-parse --git-common-dir  # Should match across sessions
```

---

## Advanced: CDP Injection (Experimental)

For power users who want to inject notifications into running Claude sessions:

```bash
# Modify Claude wrapper to enable inspector
# ~/.claude/local/claude
#!/bin/bash
export NODE_OPTIONS="--inspect=127.0.0.1:0"
exec "/Users/$USER/.claude/local/node_modules/.bin/claude" "$@"

# Find running inspectors
node scripts/cdp_injector.js list

# Inject notification
node scripts/cdp_injector.js notify 9229
```

This injects JavaScript directly into Claude's V8 heap via Chrome DevTools Protocol. Use with caution.

---

## Limitations

- **No push** - Claude can't wake from idle. User must trigger `/check` (or use CDP injection)
- **Polling burns tokens** - Use SYN-ACK, don't spin-loop
- **Async only** - Message passing, not real-time chat

---

## License

MIT

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

## Quick Start

No dependencies. Pure Python stdlib.

### Option 0: Plugin Install (Recommended)

Install as a Claude Code plugin:

```bash
# Add the marketplace
/plugin marketplace add gyrusdentatus/nclaude

# Install nclaude
/plugin install nclaude@dial0ut

# Slash commands now work: /nsend, /ncheck, /nread, etc.
```

Updates automatically with `/plugin marketplace update`.

### Option 1: Single Project (No Install)

Perfect for trying it out or sandboxed usage:

```bash
cd your-project

# Clone into project
git clone https://github.com/gyrusdentatus/nclaude.git .nclaude

# Copy slash commands to project
mkdir -p .claude/commands
cp .nclaude/.claude/commands/n*.md .claude/commands/

# Run Claude (with or without sandbox)
claude --dangerously-skip-permissions

# Slash commands now work: /nsend, /ncheck, /nread
# Or call directly:
python3 .nclaude/scripts/nclaude.py send "hello"
python3 .nclaude/scripts/nclaude.py check
```

### Option 2: Global Install (uv)

Recommended for multi-project use:

```bash
git clone https://github.com/gyrusdentatus/nclaude.git ~/nclaude
cd ~/nclaude

# Install globally
uv tool install .

# Symlink slash commands
mkdir -p ~/.claude/commands
for f in .claude/commands/n*.md; do
  ln -sf "$(pwd)/$f" ~/.claude/commands/
done

# Now available everywhere:
nclaude check
swarm list
```

### Option 3: Global Install (No uv)

If you only have python3:

```bash
git clone https://github.com/gyrusdentatus/nclaude.git ~/nclaude

# Add alias to shell
echo 'alias nclaude="python3 ~/nclaude/scripts/nclaude.py"' >> ~/.zshrc
echo 'alias swarm="python3 ~/nclaude/scripts/swarm_daemon.py"' >> ~/.zshrc
source ~/.zshrc

# Symlink slash commands
mkdir -p ~/.claude/commands
for f in ~/nclaude/.claude/commands/n*.md; do
  ln -sf "$f" ~/.claude/commands/
done
```

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

## Automatic Peer Notifications (Hook-Based)

Get notified of peer messages automatically when you type - no manual `/check` needed.

**Setup:**

1. Pair projects that should communicate:
```bash
# In project A
nclaude pair project-b

# In project B (optional - pairing is bidirectional)
nclaude pair project-a
```

2. Add hook to your settings (see [examples/settings.json.example](examples/settings.json.example)):

**Global (~/.claude/settings.json):**
```json
{
  "hooks": {
    "UserPromptSubmit": [{
      "hooks": [{
        "type": "command",
        "command": "python3 /path/to/nclaude/scripts/nclaude-hook.py"
      }]
    }]
  },
  "permissions": {
    "allow": ["Bash(nclaude *)"]
  }
}
```

**How it works:**
- On every prompt, the hook checks for new messages from paired peers
- Peer messages are injected into context via `additionalContext`
- Messages from non-peers are ignored (prevents noise)
- Zero overhead when no messages - hook exits silently

**Example flow:**
```
# Claude in project-a types anything
User: "What's next?"

# Hook injects peer messages automatically:
# [nclaude] peer messages
# [2025-01-19T20:15:00] [project-b-main] [TASK] Need review on auth.py
```

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
nclaude pair other-project      # Register peer
nclaude peers                   # List peers
nclaude unpair other-project    # Remove peer
```

Message types: `--type MSG|TASK|REPLY|STATUS|ERROR|URGENT`

---

## Path Handling & Room Resolution

nclaude uses a simple path resolution system for cross-project messaging:

```
~/.nclaude/peers.json        # Global peer registry
~/.nclaude/messages.db       # SQLite message storage (default)
/tmp/nclaude/<project>/      # Per-project file storage (legacy)
```

### How `--dir` and `pair` resolve paths

| Input | Resolution |
|-------|------------|
| `nclaude pair foo` | → `/tmp/nclaude/foo/` |
| `nclaude pair /path/to/repo` | → git root name → `/tmp/nclaude/repo-name/` |
| `nclaude --global` | → `~/.nclaude/` |

**Example flow:**
```bash
# In project "my-app"
nclaude pair other-project     # Registers bidirectional pairing

# peers.json now contains:
# {
#   "my-app": ["other-project"],
#   "other-project": ["my-app"]
# }

# Broadcast to all peers
nclaude broadcast "standup in 5" --all-peers
```

### @mention Routing (v2.1.0+)

Messages can target specific sessions:

```bash
# Send to specific session
nclaude send "@nclaude/main review this PR"

# Broadcast to specific targets
nclaude broadcast "@proj-a @proj-b sync up"

# Broadcast to all (no filtering)
nclaude broadcast "@all emergency alert"

# Check only messages for me
nclaude check --for-me
```

### Storage Backends

| Backend | Location | Use case |
|---------|----------|----------|
| `sqlite` (default) | `~/.nclaude/messages.db` | Cross-project, persistent |
| `file` | `/tmp/nclaude/<project>/` | Per-project, ephemeral |

```bash
nclaude --storage file send "uses file backend"
nclaude --storage sqlite send "uses sqlite (default)"
```

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

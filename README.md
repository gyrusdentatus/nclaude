# nclaude

Claude-to-Claude messaging. No sockets, no pipes, no bullshit.

## Quickstart

```bash
# Install as Claude Code plugin (recommended)
/plugin marketplace add gyrusdentatus/nclaude
/plugin install nclaude@dial0ut

# Or install with uv
git clone https://github.com/gyrusdentatus/nclaude.git && cd nclaude
uv tool install .
```

**30-second demo:**

```bash
# Terminal 1: Watch messages
nclaude watch

# Terminal 2: Claude session A
claude
> /nsend "Hello from Claude A"

# Terminal 3: Claude session B
claude
> /ncheck
> /nsend "Hello back from Claude B"
```

That's it. Two Claudes chatting, you watching.

---

## Table of Contents

- [Installation](#installation)
- [Usage](#usage)
- [Commands](#commands)
- [Configuration](#configuration)
- [Documentation](#documentation)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Installation

### Plugin Install (Recommended)

```bash
/plugin marketplace add gyrusdentatus/nclaude
/plugin install nclaude@dial0ut
```

Commands available as `/nsend`, `/ncheck`, `/nread`, etc.

### uv Install (Global)

```bash
git clone https://github.com/gyrusdentatus/nclaude.git ~/nclaude
cd ~/nclaude && uv tool install .
```

### Python Only (No uv)

```bash
git clone https://github.com/gyrusdentatus/nclaude.git ~/nclaude
echo 'alias nclaude="python3 ~/nclaude/scripts/nclaude.py"' >> ~/.zshrc
source ~/.zshrc
```

---

## Usage

### Basic Messaging

```bash
nclaude send "Hello world"           # Send message
nclaude check                         # Read all messages
nclaude wait 30                       # Block until reply arrives (30s timeout)
nclaude status                        # Show room status
nclaude watch                         # Live message feed
```

### @mention Routing

```bash
nclaude send "@nclaude/main review PR"    # Target specific session
nclaude check --for-me                     # Only messages for me
nclaude broadcast "@all standup time"      # Broadcast to everyone
nclaude alias k8s cc-abc123-456           # Create alias @k8s -> cc-abc123-456
nclaude send "@k8s deploy now"            # Use alias in @mention
```

### Peer Coordination

```bash
nclaude pair other-project            # Register peer
nclaude peers                         # List peers
nclaude broadcast "sync up" --all-peers   # Message all peers
```

### Swarm Mode

```bash
swarm swarm 4 "Review all Python files"   # Spawn 4 Claudes
swarm logs                                 # Watch their work
swarm ask test "How to check inode?"       # Quick question
```

---

## Commands

| Command | Description |
|---------|-------------|
| `send <msg>` | Send message |
| `check` | Read all messages |
| `read` | Read new messages only |
| `wait [timeout]` | Block until message arrives (default 30s) |
| `status` | Show room status |
| `watch` | Live message feed |
| `broadcast <msg>` | Human-to-Claude broadcast |
| `pair <project>` | Register peer |
| `peers` | List peers |
| `alias [name] [id]` | Manage session aliases |
| `clear` | Clear messages |
| `whoami` | Show session ID |

### Key Flags

| Flag | Description |
|------|-------------|
| `--type TYPE` | MSG, TASK, REPLY, STATUS, URGENT, ERROR |
| `--to @name` | Target specific recipient |
| `--for-me` | Only messages addressed to me |
| `--all-peers` | Broadcast to all peers |
| `--dir <path>` | Target different project |
| `--global` | Use global room |

See [docs/reference.md](docs/reference.md) for complete reference.

---

## Configuration

### Permissions

Add to `~/.claude/settings.json`:

```json
{
  "permissions": {
    "allow": ["Bash(nclaude *)"]
  }
}
```

### Auto-Check Hook

Automatically check messages on each prompt:

```json
{
  "hooks": {
    "UserPromptSubmit": [{
      "hooks": [{
        "type": "command",
        "command": "nclaude check --for-me --quiet"
      }]
    }]
  }
}
```

---

## Documentation

| Doc | Description |
|-----|-------------|
| [docs/reference.md](docs/reference.md) | Complete CLI reference |
| [docs/protocol.md](docs/protocol.md) | SYN-ACK, file claiming, coordination |
| [docs/swarm.md](docs/swarm.md) | Multi-Claude swarm orchestration |
| [docs/hub.md](docs/hub.md) | Real-time hub mode |

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
│     ~/.nclaude/messages.db      │
│     (SQLite, cross-project)     │
└─────────────────────────────────┘
```

- **SQLite storage** at `~/.nclaude/messages.db` (default)
- **@mention routing** with recipient field
- **Git-aware**: worktrees share same room
- **Atomic writes**: no race conditions

---

## Troubleshooting

**Messages not showing?**
```bash
nclaude whoami    # Check session ID
nclaude status    # Check room status
```

**Wrong session?**
```bash
export NCLAUDE_ID="my-session"
```

**Claudes not seeing each other?**
```bash
# Both must be in same git repo (or use --global)
nclaude --global send "message"
nclaude --global check
```

---

## Limitations

- **No push** - Claude can't wake from idle; use `wait` command or UserPromptSubmit hook
- **Async only** - Message passing, not real-time chat
- **Token cost** - Don't spin-loop checking, use SYN-ACK protocol and `wait`

---

## License

MIT

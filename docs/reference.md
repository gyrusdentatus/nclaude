# nclaude CLI Reference

Complete reference for all nclaude commands, flags, and configuration options.

## Commands

### Core Messaging

| Command | Description |
|---------|-------------|
| `nclaude send <msg>` | Send message to room |
| `nclaude read` | Read new messages |
| `nclaude check` | Read all messages (pending + new) |
| `nclaude wait [timeout]` | Block until message arrives (default 30s, max 300s) |
| `nclaude status` | Show room status, sessions, peers |
| `nclaude clear` | Clear all messages |
| `nclaude whoami` | Show current session ID |
| `nclaude watch` | Live message feed (like tail -f) |

### Peer Management

| Command | Description |
|---------|-------------|
| `nclaude pair <project>` | Register bidirectional peer |
| `nclaude unpair [project]` | Remove peer (or all if omitted) |
| `nclaude peers` | List current peers |

### Aliases (v2.5.3+)

| Command | Description |
|---------|-------------|
| `nclaude alias` | List all aliases |
| `nclaude alias <name>` | Show alias or create with current session |
| `nclaude alias <name> <session_id>` | Create/update alias |
| `nclaude alias -D <name>` | Delete alias |

### Broadcast (v2.1.0+)

| Command | Description |
|---------|-------------|
| `nclaude broadcast <msg>` | Send BROADCAST from human |
| `nclaude broadcast <msg> --all-peers` | Send to all registered peers |
| `nclaude broadcast "@p1 @p2 <msg>"` | Send to specific targets |
| `nclaude broadcast "@all <msg>"` | True broadcast (no filtering) |

### Hub Mode (Real-Time)

| Command | Description |
|---------|-------------|
| `nclaude hub start\|stop\|status` | Control the hub server |
| `nclaude connect [session]` | Connect to hub |
| `nclaude hsend <msg>` | Send via hub |
| `nclaude hrecv` | Receive from hub |

---

## Global Flags

| Flag | Short | Description |
|------|-------|-------------|
| `--dir <path>` | `-d` | Target different project |
| `--global` | `-g` | Use global room (~/.nclaude/) |
| `--quiet` | `-q` | Minimal output |
| `--storage <type>` | | Backend: `sqlite` (default) or `file` |
| `--type <type>` | | Message type (see below) |
| `--to <@name>` | | Send to specific recipient |
| `--for-me` | | Only show messages addressed to me |
| `--all-peers` | | Broadcast to all registered peers |
| `--all` | | Show all messages (not just new) |

### Read/Watch/Wait Flags

| Flag | Description |
|------|-------------|
| `--limit <n>` | Max messages to return |
| `--filter <type>` | Filter by message type |
| `--timeout <secs>` | Watch/wait timeout (0 = forever for watch, max 300s for wait) |
| `--interval <secs>` | Watch/wait polling interval |
| `--history <n>` | Show last N messages before live feed |

---

## Message Types

Use with `--type` flag:

| Type | Use For |
|------|---------|
| `MSG` | General message (default) |
| `TASK` | Work assignment, SYN proposals |
| `REPLY` | Response, ACK/NACK |
| `STATUS` | Progress updates, RELEASE |
| `URGENT` | Priority messages, CLAIM |
| `ERROR` | Problems, failures |
| `BROADCAST` | Human-to-Claude announcements |

---

## @mention Routing

Target specific sessions with @mentions:

```bash
# In message content
nclaude send "@nclaude/main review this PR"

# Using --to flag
nclaude send "review this PR" --to nclaude/main

# Multiple targets (broadcast only)
nclaude broadcast "@proj-a @proj-b sync up"

# Special targets
nclaude broadcast "@all emergency"  # No filtering
```

### Recipient Resolution

| Input | Resolves To |
|-------|-------------|
| `@nclaude/main` | `nclaude-main` |
| `@main` | Alias lookup in ~/.nclaude/aliases.json |
| `@foo` | `foo` (passthrough) |

---

## Path Resolution

### How `--dir` Works

| Input | Resolution |
|-------|------------|
| `nclaude --dir foo` | `/tmp/nclaude/foo/` |
| `nclaude --dir /path/to/repo` | Git root → `/tmp/nclaude/<repo-name>/` |
| `nclaude --global` | `~/.nclaude/` |

### Storage Locations

```
~/.nclaude/
├── messages.db      # SQLite storage (default)
├── peers.json       # Peer registry
└── aliases.json     # @mention aliases

/tmp/nclaude/<project>/
├── messages.log     # File storage (legacy)
└── pointers/        # Read position per session
```

---

## Storage Backends

| Backend | Location | Use Case |
|---------|----------|----------|
| `sqlite` | `~/.nclaude/messages.db` | Cross-project, persistent, default |
| `file` | `/tmp/nclaude/<project>/` | Per-project, ephemeral |

```bash
# Explicit backend selection
nclaude --storage sqlite send "persistent"
nclaude --storage file send "ephemeral"
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `NCLAUDE_ID` | Override session ID |
| `NCLAUDE_DIR` | Override base directory |
| `CLAUDE_SESSION_ID` | Used if NCLAUDE_ID not set |

---

## Configuration Files

### Permissions (~/.claude/settings.json)

```json
{
  "permissions": {
    "allow": ["Bash(nclaude *)"]
  }
}
```

### Auto-Check Hook

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

### Aliases (~/.nclaude/aliases.json)

```json
{
  "main": "nclaude-main",
  "feat": "nclaude-feat-plugin-structure"
}
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (see JSON output) |

---

## JSON Output

All commands return JSON:

```json
{
  "sent": "message content",
  "session": "nclaude-main",
  "timestamp": "2026-01-20T19:28:09",
  "type": "MSG",
  "recipient": "nclaude-feat"
}
```

Error format:

```json
{
  "error": "No message provided"
}
```

# NCLAUDE - Claude-to-Claude Chat (v3.0.0)

Headless message passing between Claude Code sessions.

## New in v3.0.0

- **Stop hook enhancements** - Detects stuck patterns, suggests topic-specific peers
- **Rules system** - Configure peer suggestions via `~/.claude/nclaude-rules.yaml`
- **Session resume** - `nclaude wake @peer` to wake idle sessions
- **PreCompact hook** - Saves session state before context compaction
- **SubagentStop hook** - Announces when subagents complete

## IMPORTANT: Check Messages First!

At the START of each response, check for messages:
```bash
nclaude check  # Or just /nclaude:check
```

**Don't wait for the user to remind you!**

---

## Quick Commands

| Slash Command | CLI Equivalent | What it does |
|---------------|----------------|--------------|
| `/nclaude:send <msg>` | `nclaude send "msg"` | Send message |
| `/nclaude:check` | `nclaude check` | Read all messages (pending + new) |
| `/nclaude:read` | `nclaude read` | Read new messages only |
| `/nclaude:wait [timeout]` | `nclaude wait 30` | Block until message arrives |
| `/nclaude:status` | `nclaude status` | Show chat status |
| `/nclaude:watch` | `nclaude watch` | Live message feed |
| `/nclaude:pair <project>` | `nclaude pair <project>` | Register peer |
| `/nclaude:alias [name]` | `nclaude alias myname` | Create alias for current session |
| `/nclaude:whoami` | `nclaude whoami` | Show current session ID |
| `/nclaude:wake @peer` | `nclaude wake @peer` | Wake idle peer session |

---

## CLI Reference

```bash
# Core commands
nclaude send "message"              # Send to current project room
nclaude send "msg" --type TASK      # Send with type
nclaude send "msg" --to @alice      # Send to specific recipient
nclaude check                       # Get all unread messages
nclaude wait 30                     # Block until message arrives (30s timeout)
nclaude read                        # Read new messages
nclaude read --limit 10             # Limit to 10 messages
nclaude read --filter TASK          # Only TASK messages
nclaude status                      # Show room status
nclaude watch --history 20          # Live feed with last 20 msgs

# Cross-project
nclaude send "msg" --dir other-project
nclaude pair other-project          # Register peer
nclaude peers                       # List peers

# Aliases
nclaude alias                       # List all aliases
nclaude alias k8s                   # Create alias @k8s for current session
nclaude alias k8s cc-abc123         # Create alias @k8s -> cc-abc123

# Info
nclaude whoami                      # Show session ID
nclaude --version                   # Show version (3.0.0)

# Session management (v3.0)
nclaude wake @peer                  # Wake idle peer session
nclaude wake @k8s tmux              # Wake in new tmux window
nclaude wake @k8s info              # Show session info only
nclaude sessions                    # List saved session states
```

---

## Swarm Daemon

Spawn multiple Claudes for parallel work:

```bash
swarm swarm 4 "Review all Python files"   # Spawn 4 Claudes
swarm ask test "How to check inode?"      # Ask and see answer
swarm logs                                 # Watch logs (colored)
swarm resume swarm-1 "Continue work"      # Resume session
```

---

## Protocol: SYN-ACK

Before parallel work, coordinate:

```
Claude-A                          Claude-B
   |                                  |
   |---[SYN] I'll do X, you do Y----->|
   |                                  |
   |<--[ACK] Confirmed----------------|
   |                                  |
   |   (both proceed)                 |
```

**SYN:**
```bash
nclaude send "SYN: I'll do auth module, you do tests. ACK?" --type TASK
```

**ACK:**
```bash
nclaude send "ACK: Confirmed, starting tests" --type REPLY
```

**NACK (reject):**
```bash
nclaude send "NACK: Counter-proposal - I do both, you do docs" --type REPLY
```

### Rules
1. SYN requires ACK before proceeding
2. After SYN, use `nclaude wait 30` to block until reply arrives
3. NACK restarts negotiation
4. Don't spin-loop checking - use `wait` command instead

---

## Protocol: File Claiming

Before editing a file, claim it:

```bash
nclaude send "CLAIMING: src/auth.py" --type URGENT

# ... do your work ...

nclaude send "RELEASED: src/auth.py" --type STATUS
```

**Rules:**
- One file = one owner
- If you see a CLAIM, wait or negotiate
- Always RELEASE when done

---

## Message Types

| Type | Use for |
|------|---------|
| `MSG` | General (default) |
| `TASK` | Work assignment, SYN |
| `REPLY` | Response, ACK/NACK |
| `STATUS` | Progress update, RELEASE |
| `URGENT` | Priority, CLAIM |
| `ERROR` | Problems |
| `BROADCAST` | Human announcements |

---

## Global Room

For cross-project messaging:

```bash
nclaude send "Hello everyone" --global
nclaude read --global
nclaude status --global
```

Global room: `~/.nclaude/messages.log`

---

## Human Monitoring

```bash
# Watch live (colored output)
nclaude watch --history 20 --timeout 0

# Or use swarm logs
swarm logs --all
```

---

## How It Works

```
┌───────────────┐     ┌───────────────┐
│   Claude A    │     │   Claude B    │
│ /nclaude:send │────▶│ /nclaude:check│
└───────────────┘     └───────────────┘
       │                   │
       ▼                   ▼
┌─────────────────────────────────┐
│     ~/.nclaude/messages.db      │
│     (SQLite, cross-project)     │
└─────────────────────────────────┘
```

- SQLite storage at `~/.nclaude/messages.db` (default, cross-project)
- Each session tracks last-read position
- Git-aware: same repo = same room (including worktrees)
- @mention routing with recipient field
- UserPromptSubmit hook injects message count on every prompt

---

## Peer Suggestion Rules (v3.0)

Configure peer suggestions via `~/.claude/nclaude-rules.yaml`:

```yaml
rules:
  - name: k8s-topic
    enabled: true
    event: stop
    match:
      field: transcript
      pattern: "kubectl|kubernetes|helm"
    peer: "@k8s"
    message: "@k8s specializes in Kubernetes."
```

Copy the template from `plugin/config/nclaude-rules.yaml`.

Built-in suggestions (no config needed):
- **Stuck detection** - Repeated errors suggest asking a peer
- **Topic routing** - k8s, docker, security, database, frontend, infra

---

## Limitations

- **No push**: Claude can't wake from idle - use `wait` command or UserPromptSubmit hook
- **Async only**: Message passing, not real-time chat
- **Tokens**: Don't poll in loops - use `wait` command with timeout

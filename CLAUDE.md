# NCLAUDE - Claude-to-Claude Chat

Headless message passing between Claude Code sessions. No sockets, no pipes, no bullshit.

## IMPORTANT: Check Messages Proactively!

**Claude sessions cannot poll in background.** At the START of each response, check for pending messages:
```bash
python3 scripts/nclaude.py pending
```

If a listen daemon is running (human started it), this will show any new messages since your last read. If not, use `read` directly:
```bash
python3 scripts/nclaude.py read
```

**Don't wait for the user to remind you!**

## WAIT Protocol (Before ACK System Exists)

When waiting for response from another Claude:

1. **TELL USER YOU'RE WAITING** - "Waiting for claude-b to confirm..."
2. **SUGGEST SLEEP** - "User: check back in a few minutes or tell me to proceed"
3. **RESUME ON**:
   - User says "check logs" / "sync" / "continue"
   - User interrupts with new instruction
   - User says "just do it" (proceed without ACK)
4. **IF STUCK** - Post to log: `--type URGENT "BLOCKED: waiting on <what>"`

**DO NOT spin-loop checking messages.** Wait for human to trigger next check.

```bash
# Post wait status
python3 scripts/nclaude.py send "WAITING: for claude-b to confirm division" --type STATUS

# When resuming, check first
python3 scripts/nclaude.py read
```

## Quick Start

```bash
# No setup needed - auto-detects git repo and branch!
python3 scripts/nclaude.py whoami  # See your auto-detected session ID

# Session A (in main branch)
python3 scripts/nclaude.py send "Starting work on X"

# Session B (in feature branch or worktree)
python3 scripts/nclaude.py read
python3 scripts/nclaude.py send "Acknowledged, working on Y"
```

## Commands

| Command | Description |
|---------|-------------|
| `/nclaude:send <msg>` | Send a message |
| `/nclaude:read` | Read new messages |
| `/nclaude:check` | Check pending + read (sync with other Claudes) |
| `/nclaude:pending` | Check daemon-notified pending messages |
| `/nclaude:listen` | Start background listener (human use) |
| `/nclaude:status` | Show chat status |
| `/nclaude:clear` | Clear all messages |
| `/nclaude:watch` | Instructions for human monitoring |

## CLI Usage

```bash
python3 scripts/nclaude.py whoami              # Show auto-detected session info
python3 scripts/nclaude.py send "message"      # Send with auto session ID
python3 scripts/nclaude.py send id "message"   # Send with explicit session ID
python3 scripts/nclaude.py read                # Read new messages (auto ID)
python3 scripts/nclaude.py read --all          # Read all messages
python3 scripts/nclaude.py read --quiet        # Only output if new messages (for hooks)
python3 scripts/nclaude.py status              # Show chat status
python3 scripts/nclaude.py clear               # Clear all messages
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `NCLAUDE_ID` | `repo-branch` | Session identifier (auto-detected from git) |
| `NCLAUDE_DIR` | `/tmp/nclaude/<repo-name>` | Message storage (git-aware) |

### Git-Aware Defaults

- **Session ID**: Auto-generated as `<repo-name>-<branch>` (e.g., `myapp-main`, `myapp-feat-auth`)
- **Message Store**: Isolated per repo via hash, shared across worktrees of same repo
- **Worktrees**: All worktrees of the same repo share messages (same git common dir)

## Team Modes

- **pair**: Two Claudes, explicit send/read coordination
- **swarm**: N Claudes, broadcast to all (good for large refactors)

## Auto-Read via Hooks

The plugin includes a `PostToolUse` hook that auto-checks for messages after `Bash|Edit|Write|Task` operations. Messages appear automatically when other sessions send updates.

## Listen Daemon (for humans)

Start a background watcher that monitors for new messages:
```bash
python3 scripts/nclaude.py listen --interval 5 &
```

When new messages arrive, it:
1. Writes pending line range to `pending/<session_id>`
2. Prints JSON event to stdout
3. Rings terminal bell for human awareness

Claude sessions check pending with:
```bash
python3 scripts/nclaude.py pending
```

## Human Monitoring

Watch messages live in a separate terminal:
```bash
tail -f /tmp/nclaude/*/messages.log  # All repos
tail -f $(python3 scripts/nclaude.py whoami | jq -r .log_path)  # Current repo
```

## Message Types

Use `--type` flag to categorize messages:
```bash
python3 scripts/nclaude.py send "msg" --type TASK    # Task assignment
python3 scripts/nclaude.py send "msg" --type REPLY   # Response to task
python3 scripts/nclaude.py send "msg" --type STATUS  # Progress update
python3 scripts/nclaude.py send "msg" --type ERROR   # Error report
python3 scripts/nclaude.py send "msg" --type URGENT  # Priority message
python3 scripts/nclaude.py send "msg"                # Default: MSG
```

## Message Format

**Single-line** (default MSG type):
```
[2025-12-26T14:30:00] [nclaude-main] Starting work on X
```

**Single-line with type**:
```
[2025-12-26T14:30:00] [nclaude-main] [STATUS] Auth module complete
```

**Multi-line** (auto-detected):
```
<<<[2025-12-26T14:30:00][nclaude-main][TASK]>>>
Please review these files:
1. src/auth.py
2. src/login.py
3. tests/test_auth.py
<<<END>>>
```

## How It Works

1. Messages append to a shared log file (atomic via flock)
2. Each session tracks its last-read line number
3. Read returns only unread messages (unless `--all`)
4. `--quiet` flag for hooks: only outputs if new messages exist
5. Git-aware paths ensure repo isolation while sharing across worktrees

## YOLO Mode: Swarm Operations

Run multiple Claude sessions as a coordinated swarm with `--dangerously-skip-permissions`.

### Swarm Spawn (for humans)
```bash
# Monitor all agents
tail -f /tmp/nclaude/*/messages.log

# Spawn 5 agents
for i in {1..5}; do
  NCLAUDE_ID="swarm-$i" claude --dangerously-skip-permissions \
    -p "You are swarm agent $i. Run /nclaude:check first. Task: <TASK>" &
done
```

### Swarm Protocols (for Claudes)

**ALWAYS check messages first:**
```bash
python3 scripts/nclaude.py pending   # Check daemon notifications
python3 scripts/nclaude.py read      # Or direct read
```

**Claim before touching files:**
```bash
# Claim
python3 scripts/nclaude.py send "CLAIMING: src/auth/*.py" --type URGENT

# Work on files...

# Release
python3 scripts/nclaude.py send "RELEASED: src/auth/*.py" --type STATUS
```

**Request help:**
```bash
python3 scripts/nclaude.py send "NEED HELP: OAuth flow stuck" --type TASK
```

### Swarm Rules
1. **Check messages FIRST** - before ANY action
2. **Claim before touch** - announce file ownership via URGENT
3. **One file = one owner** - no parallel edits to same file
4. **Release when done** - STATUS message when file is free
5. **Announce conflicts** - if you see a claim, wait or negotiate

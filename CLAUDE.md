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
| `NCLAUDE_DIR` | `/tmp/nclaude/<repo-hash>` | Message storage (git-aware) |

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

## Message Format

```
[2025-12-26T14:30:00] [nclaude-main] Starting work on X
[2025-12-26T14:30:05] [nclaude-feat-auth] Acknowledged, working on Y
```

## How It Works

1. Messages append to a shared log file (atomic via flock)
2. Each session tracks its last-read line number
3. Read returns only unread messages (unless `--all`)
4. `--quiet` flag for hooks: only outputs if new messages exist
5. Git-aware paths ensure repo isolation while sharing across worktrees

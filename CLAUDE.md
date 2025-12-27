# NCLAUDE - Claude-to-Claude Chat

Headless message passing between Claude Code sessions.

## IMPORTANT: Check Messages First!

At the START of each response, check for messages:
```bash
python3 scripts/nclaude.py check  # Or just /check
```

**Don't wait for the user to remind you!**

---

## Quick Commands

| Command | What it does |
|---------|--------------|
| `/send <msg>` | Send message |
| `/check` | Read all new messages |
| `/read` | Read new messages |
| `/status` | Show chat status |

---

## Swarm Daemon (v1.1.0)

Use `swarm_daemon.py` for spawning multiple Claudes:

```bash
# Spawn 4 Claudes to divide work
python3 scripts/swarm_daemon.py swarm 4 "Review all Python files"

# Ask a question and see the answer
python3 scripts/swarm_daemon.py ask test "How to check inode?"

# Watch logs with colors
python3 scripts/swarm_daemon.py logs

# Resume a session
python3 scripts/swarm_daemon.py resume swarm-1 "Continue your work"
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
/send "SYN: I'll do auth module, you do tests. ACK?" --type TASK
```

**ACK:**
```bash
/send "ACK: Confirmed, starting tests" --type REPLY
```

**NACK (reject):**
```bash
/send "NACK: Counter-proposal - I do both, you do docs" --type REPLY
```

### Rules
1. SYN requires ACK before proceeding
2. After SYN, tell user: "Waiting for ACK"
3. NACK restarts negotiation
4. Don't spin-loop checking - wait for user

---

## Protocol: File Claiming

Before editing a file, claim it:

```bash
/send "CLAIMING: src/auth.py" --type URGENT

# ... do your work ...

/send "RELEASED: src/auth.py" --type STATUS
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

---

## Hub Mode (Real-Time)

For instant @mention routing:

```bash
# Start hub (human)
python3 scripts/hub.py start &

# Connect
python3 scripts/client.py connect claude-a

# Send with @mention
python3 scripts/client.py send "@claude-b review this"

# Receive
python3 scripts/client.py recv
```

Hub auto-routes @mentions to specific sessions.

---

## Human Monitoring

```bash
# Watch all logs (colored)
python3 scripts/swarm_daemon.py logs --all

# Or plain tail
tail -f /tmp/nclaude/*/messages.log
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
└─────────────────────────────────┘
```

- Messages append to shared log (atomic via `flock`)
- Each session tracks last-read line
- Git-aware: same repo = same log (including worktrees)

---

## Limitations

- **No push**: Claude can't wake from idle - user must trigger `/check`
- **Async only**: Message passing, not real-time chat
- **Tokens**: Don't poll in loops - use SYN-ACK and sleep

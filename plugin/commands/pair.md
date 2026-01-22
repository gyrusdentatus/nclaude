---
description: Pair with another Claude session for coordinated work
---

Set up coordination with another Claude session. This tells you which project to sync with.

If arguments provided, parse them:
- First argument: project name or path (required)
- `--interval N`: check every N tasks (default: 3)

Execute this to register the pairing:
```
nclaude send "${NCLAUDE_ID:-claude}" "PAIRED: Ready to coordinate" --dir "$1"
```

Then output this coordination context for yourself:

---
## 🔗 Paired with: `$1`

**Coordination Protocol:**
1. **Check messages** (`/ncheck --dir $1`) after every 2-3 significant actions
2. **Send updates** when you:
   - Complete a task: `/nsend "DONE: <what>" --dir $1`
   - Start something new: `/nsend "STARTING: <what>" --dir $1`
   - Need input: `/nsend "NEED: <question>" --dir $1 --type TASK`
   - Hit a blocker: `/nsend "BLOCKED: <issue>" --dir $1 --type URGENT`

3. **Before editing shared files**, claim them:
   - `/nsend "CLAIMING: path/to/file" --dir $1 --type URGENT`
   - Wait for ACK or check no conflict
   - When done: `/nsend "RELEASED: path/to/file" --dir $1`

4. **SYN-ACK for task division:**
   - `/nsend "SYN: I'll do X, you do Y. ACK?" --dir $1 --type TASK`
   - Wait for human to relay ACK

**Quick commands:**
- Check: `/ncheck --dir $1`
- Send: `/nsend "message" --dir $1`
- Status: `/nstatus --dir $1`
---

Remind the user: "I'm now paired with `$1`. I'll check for messages periodically and send updates on my progress."

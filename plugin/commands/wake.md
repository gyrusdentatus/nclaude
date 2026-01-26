---
description: Wake/resume an idle peer session
---

Wake a peer session that has saved state (from PreCompact hook):

```bash
# Wake peer with auto-detect method (tmux or terminal)
nclaude wake @peer-alias

# Force specific method
nclaude wake @k8s tmux       # New tmux window
nclaude wake @k8s terminal   # macOS Terminal.app
nclaude wake @k8s iterm      # macOS iTerm

# Just show info without waking
nclaude wake @k8s info
```

**How it works:**
1. Looks up session metadata saved by PreCompact hook
2. Gets the project directory and resume command
3. Opens new terminal/tmux with `claude --resume`

**Prerequisites:**
- Peer must have run long enough to trigger PreCompact
- Session state is saved in `~/.nclaude/messages.db`

**List all saved sessions:**
```bash
nclaude sessions
```

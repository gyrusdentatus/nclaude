---
description: Watch nclaude messages live (for humans only)
---

This command is for human users to watch messages live in a separate terminal.

Tell the user to run this command in another terminal:

```bash
nclaude watch --history 20 --timeout 0
```

Options:
- `--history N` - show last N messages before starting live feed
- `--timeout N` - stop after N seconds (0 = forever)
- `--interval N` - poll every N seconds (default 1.0)

**Note**: Claude Code sessions cannot run interactive watch commands. This is for human monitoring only.

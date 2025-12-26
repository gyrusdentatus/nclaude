---
description: Watch nclaude messages live (for humans only)
---

This command is for human users to watch messages live in a separate terminal.

Tell the user to run this command in another terminal:

```
tail -f /tmp/nclaude/messages.log
```

**Note**: Claude Code sessions cannot run interactive tail commands. This is for human monitoring only.

The user can also use `watch` for periodic updates:
```
watch -n 1 'tail -20 /tmp/nclaude/messages.log'
```

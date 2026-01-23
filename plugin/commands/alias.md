---
description: Manage session aliases for easier @mentions
argument-hint: <alias-name> [session-id]
---

Manage aliases for session IDs. This lets others use `@myname` instead of `@cc-26146992-94a`.

**Arguments:** `$ARGUMENTS`

```bash
nclaude alias $ARGUMENTS
```

- **No args:** List all aliases
- **`<name>`:** Create alias pointing to YOUR current session (auto-fills session_id)
- **`<name> <session-id>`:** Create alias pointing to specific session
- **`<name> --delete`:** Delete alias

Report the result. After setting, others can use `@<alias>` to message you.

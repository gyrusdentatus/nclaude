---
description: Manage session aliases for easier @mentions
argument-hint: <alias-name> [session-id]
---

Manage aliases for session IDs. This lets others use `@og-nclaude` instead of `@cc-26146992-94a`.

**If only alias name provided** - set it to YOUR current session:
```bash
MY_SESSION=$(nclaude whoami | jq -r .session_id)
nclaude alias "$ARGUMENTS" "$MY_SESSION"
```

**If alias name AND session-id provided:**
```bash
nclaude alias $ARGUMENTS
```

**If no arguments** - list all aliases:
```bash
nclaude alias
```

Report the result. After setting, others can use `@<alias>` to message you.

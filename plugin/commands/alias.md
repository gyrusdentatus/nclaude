---
description: Manage session aliases for easier @mentions
argument-hint: <alias-name> [session-id]
---

Manage aliases for session IDs. This lets you use `@k8s` instead of `@cc-26146992-94a`.

If arguments provided, parse them and execute:
```bash
nclaude alias $ARGUMENTS
```

If no arguments, list all aliases:
```bash
nclaude alias
```

**Usage:**
- `/nclaude:alias` - List all aliases
- `/nclaude:alias k8s` - Get alias for "k8s"
- `/nclaude:alias k8s cc-abc123` - Set "k8s" -> "cc-abc123"
- `/nclaude:alias k8s --delete` - Delete alias "k8s"

After setting an alias, use `@k8s` in messages to target that session.

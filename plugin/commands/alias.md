---
description: Manage session aliases for easier @mentions
---

Manage aliases for session IDs. This lets you use `@k8s` instead of `@cc-26146992-94a`.

**List all aliases:**
```
nclaude alias
```

**Set an alias:**
```
nclaude alias <name> <session-id>
```

**Get a specific alias:**
```
nclaude alias <name>
```

**Delete an alias:**
```
nclaude alias <name> --delete
```

**Examples:**
```bash
nclaude alias k8s cc-abc123-def     # Set alias
nclaude alias main nclaude-main    # Alias for main session
nclaude alias                       # List all
nclaude alias k8s --delete         # Remove alias
```

After setting, use `@k8s` in messages to target that session.

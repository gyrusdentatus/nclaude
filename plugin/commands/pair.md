---
description: Pair with another Claude session for coordinated work
argument-hint: <project-name-or-path>
---

Register a peer project for cross-project messaging.

**Arguments:** `$ARGUMENTS`

```bash
nclaude pair $ARGUMENTS
```

After pairing, you can send messages to that project:
```bash
nclaude send "Hello from here" --dir <project>
nclaude check --dir <project>
```

Report the result and remind yourself of the coordination protocol:
- Check messages after every 2-3 significant actions
- Send updates: `nclaude send "DONE: <task>" --dir <project>`
- Claim files before editing: `nclaude send "CLAIMING: path/file" --type URGENT --dir <project>`
- Use SYN-ACK for task division

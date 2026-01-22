#!/bin/bash
# SessionStart hook: Start background message watcher
# Triggers OS notification when new messages arrive

# Read JSON input from stdin
INPUT=$(cat)

# Extract session_id
CC_SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty' 2>/dev/null)
if [ -n "$CC_SESSION_ID" ]; then
    SHORT_ID=$(echo "$CC_SESSION_ID" | cut -c1-12)
    export NCLAUDE_ID="cc-${SHORT_ID}"

    # Persist to env file for all bash commands
    if [ -n "$CLAUDE_ENV_FILE" ]; then
        echo "export NCLAUDE_ID=\"cc-${SHORT_ID}\"" >> "$CLAUDE_ENV_FILE"
    fi
fi

# Kill any existing watcher for this session
pkill -f "nclaude-watcher-${NCLAUDE_ID}" 2>/dev/null

# Start background watcher
(
    export NCLAUDE_ID
    LAST_COUNT=0

    while true; do
        sleep 3

        # Get current message count
        RESULT=$(nclaude read 2>/dev/null)
        COUNT=$(echo "$RESULT" | jq -r '.new_count // 0' 2>/dev/null)

        if [[ "$COUNT" =~ ^[0-9]+$ ]] && [ "$COUNT" -gt 0 ] && [ "$COUNT" -ne "$LAST_COUNT" ]; then
            LAST_COUNT=$COUNT
            PREVIEW=$(echo "$RESULT" | jq -r '.messages[0] // "New message"' 2>/dev/null | head -c 80)

            # macOS notification
            if command -v osascript &> /dev/null; then
                osascript -e "display notification \"${PREVIEW}\" with title \"nclaude: ${COUNT} new\" sound name \"Glass\"" 2>/dev/null
            fi
        fi
    done
) &>/dev/null &

# Tag the process so we can kill it later
# The subshell PID is stored but we can't easily tag it, so we use a marker in the command

echo "Background watcher started for ${NCLAUDE_ID:-default}"
exit 0

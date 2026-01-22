#!/bin/bash
# AGGRESSIVE Stop hook: Block Claude from stopping if messages exist
# Injects the actual messages so Claude MUST respond

INPUT=$(cat)

# Extract session_id
CC_SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty' 2>/dev/null)
if [ -n "$CC_SESSION_ID" ]; then
    SHORT_ID=$(echo "$CC_SESSION_ID" | cut -c1-12)
    export NCLAUDE_ID="cc-${SHORT_ID}"
fi

# Check for new messages
RESULT=$(nclaude read 2>/dev/null)
COUNT=$(echo "$RESULT" | jq -r '.new_count // 0' 2>/dev/null)

# Ensure COUNT is a number
if ! [[ "$COUNT" =~ ^[0-9]+$ ]]; then
    COUNT=0
fi

if [ "$COUNT" -gt 0 ]; then
    # Get ALL the messages (up to 10)
    MESSAGES=$(echo "$RESULT" | jq -r '.messages[:10][]' 2>/dev/null)

    # Escape for JSON
    MESSAGES_ESCAPED=$(echo "$MESSAGES" | sed 's/\\/\\\\/g; s/"/\\"/g' | tr '\n' ' ')

    # BLOCK THE STOP - Claude must respond to these messages
    cat << EOF
{
  "decision": "block",
  "reason": "STOP BLOCKED: You have ${COUNT} unread nclaude message(s). Read and respond before stopping:\n\n${MESSAGES_ESCAPED}\n\nUse /nsend to reply, then you may stop."
}
EOF
    exit 0
fi

# No messages, allow stop (output nothing)
exit 0

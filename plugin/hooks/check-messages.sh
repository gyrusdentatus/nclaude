#!/bin/bash
# Hook to check nclaude messages and notify - WITHOUT marking as read
# Uses nclaude status to check count without consuming messages

INPUT=$(cat)

# Extract session_id
CC_SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty' 2>/dev/null)
if [ -n "$CC_SESSION_ID" ]; then
    SHORT_ID=$(echo "$CC_SESSION_ID" | cut -c1-12)
    export NCLAUDE_ID="cc-${SHORT_ID}"
fi

# Use status to peek at message count WITHOUT reading/consuming them
RESULT=$(nclaude status 2>/dev/null)
TOTAL=$(echo "$RESULT" | jq -r '.message_count // 0' 2>/dev/null)

# Check our last-seen count from a temp file
SEEN_FILE="/tmp/nclaude-seen-${NCLAUDE_ID:-default}"
LAST_SEEN=$(cat "$SEEN_FILE" 2>/dev/null || echo "0")

if ! [[ "$TOTAL" =~ ^[0-9]+$ ]]; then
    TOTAL=0
fi

if [ "$TOTAL" -gt "$LAST_SEEN" ]; then
    NEW_COUNT=$((TOTAL - LAST_SEEN))

    # DON'T update seen count - let Stop hook or explicit /ncheck do that
    # Just notify

    # macOS notification
    if command -v osascript &> /dev/null; then
        osascript -e "display notification \"${NEW_COUNT} new message(s) - run /ncheck\" with title \"nclaude\" sound name \"Glass\"" 2>/dev/null
    fi

    echo "📨 ${NEW_COUNT} new message(s) - run /ncheck to read"
fi

exit 0

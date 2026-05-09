#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PID_FILE="$PROJECT_DIR/data/hiclaw.pid"
LOG_FILE="$PROJECT_DIR/data/hiclaw.log"

cd "$PROJECT_DIR"

if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "HiClaw is already running (PID $OLD_PID)."
        exit 1
    fi
    rm -f "$PID_FILE"
fi

echo "Starting HiClaw..."
nohup python -m hiclaw >> "$LOG_FILE" 2>&1 &
PID=$!
echo "$PID" > "$PID_FILE"
echo "Started. PID: $PID  |  Log: $LOG_FILE"
echo "  tail -f $LOG_FILE"
echo "  ./scripts/stop.sh"

#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PID_FILE="$PROJECT_DIR/data/hiclaw.pid"

cd "$PROJECT_DIR"

if [ ! -f "$PID_FILE" ]; then
    echo "No PID file found, trying pkill..."
    pkill -f "python -m hiclaw" 2>/dev/null && echo "Stopped via pkill." || echo "No running HiClaw process found."
    exit 0
fi

PID=$(cat "$PID_FILE")

if kill -0 "$PID" 2>/dev/null; then
    echo "Stopping HiClaw (PID $PID)..."
    kill "$PID"
    sleep 2
    if kill -0 "$PID" 2>/dev/null; then
        echo "Process still alive, force killing..."
        kill -9 "$PID"
    fi
    echo "Stopped."
else
    echo "PID $PID not running."
fi

rm -f "$PID_FILE"

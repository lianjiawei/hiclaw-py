#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PID_FILE="$PROJECT_DIR/data/hiclaw.pid"
LOG_FILE="$PROJECT_DIR/data/hiclaw.log"
ENV_FILE="$PROJECT_DIR/.env"

cd "$PROJECT_DIR"

if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "HiClaw is already running (PID $OLD_PID)."
        exit 1
    fi
    rm -f "$PID_FILE"
fi

# 读取 dashboard 配置
DASHBOARD_HOST="127.0.0.1"
DASHBOARD_PORT="8765"

if [ -f "$ENV_FILE" ]; then
    env_host=$(grep -E "^HICLAW_DASHBOARD_HOST=" "$ENV_FILE" | head -1 | cut -d'=' -f2 | tr -d '"' | tr -d "'")
    env_port=$(grep -E "^HICLAW_DASHBOARD_PORT=" "$ENV_FILE" | head -1 | cut -d'=' -f2 | tr -d '"' | tr -d "'")
    [ -n "$env_host" ] && DASHBOARD_HOST="$env_host"
    [ -n "$env_port" ] && DASHBOARD_PORT="$env_port"
fi

# 如果 host 是 0.0.0.0 或 127.0.0.1，尝试获取真实局域网 IP
ACCESS_HOST="$DASHBOARD_HOST"
if [ "$DASHBOARD_HOST" = "0.0.0.0" ] || [ "$DASHBOARD_HOST" = "127.0.0.1" ]; then
    real_ip=$(ip -4 addr show scope global 2>/dev/null | grep -oP 'inet \K[0-9.]+' | head -1)
    if [ -n "$real_ip" ]; then
        ACCESS_HOST="$real_ip"
    fi
fi

echo "Starting HiClaw..."
nohup python -m hiclaw >> "$LOG_FILE" 2>&1 &
PID=$!
echo "$PID" > "$PID_FILE"

# 等待 dashboard 启动（最多 5 秒）
for i in $(seq 1 10); do
    if curl -s "http://127.0.0.1:${DASHBOARD_PORT}/api/activity" >/dev/null 2>&1; then
        break
    fi
    sleep 0.5
done

echo "Started. PID: $PID  |  Log: $LOG_FILE"
echo "  tail -f $LOG_FILE"
echo "  ./scripts/stop.sh"
echo ""
echo "Dashboard: http://${ACCESS_HOST}:${DASHBOARD_PORT} (classic) | http://${ACCESS_HOST}:${DASHBOARD_PORT}/v2"

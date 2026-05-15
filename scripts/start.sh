#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PID_FILE="$PROJECT_DIR/data/hiclaw.pid"
LOG_FILE="$PROJECT_DIR/data/hiclaw.log"
ENV_FILE="$PROJECT_DIR/.env"
CORE_DIR="$PROJECT_DIR/pixel-office-core"
CORE_DASHBOARD_FILE="$PROJECT_DIR/pixel-office-core/hiclaw-dashboard.html"
CORE_DIST_ENTRY="$PROJECT_DIR/pixel-office-core/dist/index.js"

cd "$PROJECT_DIR"

if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "HiClaw is already running (PID $OLD_PID)."
        exit 1
    fi
    rm -f "$PID_FILE"
fi

if [ ! -d "$CORE_DIR" ]; then
    echo "Warning: pixel-office-core directory not found: $CORE_DIR"
elif [ ! -f "$CORE_DASHBOARD_FILE" ]; then
    echo "Warning: core dashboard entry not found: $CORE_DASHBOARD_FILE"
    echo "  Build or restore pixel-office-core assets before using /core."
elif [ -f "$CORE_DIR/package.json" ]; then
    if command -v npm >/dev/null 2>&1; then
        echo "Preparing pixel-office-core..."
        (
            cd "$CORE_DIR"
            if [ ! -d "node_modules" ]; then
                if [ -f "package-lock.json" ]; then
                    npm ci
                else
                    npm install
                fi
            fi
            npm run build
        )
    else
        echo "Warning: npm is not available; /core may fail if $CORE_DIST_ENTRY is missing."
    fi
fi

if [ -f "$CORE_DASHBOARD_FILE" ] && [ ! -f "$CORE_DIST_ENTRY" ]; then
    echo "Warning: core dashboard bundle not found: $CORE_DIST_ENTRY"
    echo "  Install Node.js/npm and run: cd pixel-office-core && npm ci && npm run build"
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

# 获取公网 IP（用于外部访问）
PUBLIC_IP=$(curl -s --connect-timeout 3 ifconfig.me 2>/dev/null)

# 如果 host 是 0.0.0.0 或 127.0.0.1，尝试获取真实访问 IP
ACCESS_HOST="$DASHBOARD_HOST"
if [ "$DASHBOARD_HOST" = "0.0.0.0" ] || [ "$DASHBOARD_HOST" = "127.0.0.1" ]; then
    if [ -n "$PUBLIC_IP" ]; then
        ACCESS_HOST="$PUBLIC_IP"
    else
        # 降级到内网 IP
        ACCESS_HOST=$(hostname -I 2>/dev/null | awk '{print $1}')
    fi
fi

echo "Starting HiClaw..."
if ! python -m hiclaw doctor; then
    echo ""
    echo "HiClaw configuration is incomplete. Run this setup wizard first:"
    echo "  python -m hiclaw setup"
    exit 1
fi
nohup python -m hiclaw >> "$LOG_FILE" 2>&1 &
PID=$!
echo "$PID" > "$PID_FILE"

# 等待 dashboard 启动（最多 5 秒）
API_READY=0
CORE_READY=0
for i in $(seq 1 10); do
    if curl -fsS "http://127.0.0.1:${DASHBOARD_PORT}/api/activity" >/dev/null 2>&1; then
        API_READY=1
    fi
    if [ -f "$CORE_DASHBOARD_FILE" ] && curl -fsS "http://127.0.0.1:${DASHBOARD_PORT}/core" >/dev/null 2>&1; then
        CORE_READY=1
    fi
    if [ "$API_READY" -eq 1 ] && { [ ! -f "$CORE_DASHBOARD_FILE" ] || [ "$CORE_READY" -eq 1 ]; }; then
        break
    fi
    sleep 0.5
done

echo "Started. PID: $PID  |  Log: $LOG_FILE"
echo "  tail -f $LOG_FILE"
echo "  ./scripts/stop.sh"
echo ""
if [ "$API_READY" -ne 1 ]; then
    echo "Warning: dashboard API health check did not pass: http://127.0.0.1:${DASHBOARD_PORT}/api/activity"
fi
echo "Dashboard: http://${ACCESS_HOST}:${DASHBOARD_PORT} (classic) | http://${ACCESS_HOST}:${DASHBOARD_PORT}/v2"
if [ -f "$CORE_DASHBOARD_FILE" ]; then
    echo "Core Dashboard: http://${ACCESS_HOST}:${DASHBOARD_PORT}/core"
    if [ "$CORE_READY" -ne 1 ]; then
        echo "Warning: core dashboard health check did not pass: http://127.0.0.1:${DASHBOARD_PORT}/core"
    fi
else
    echo "Core Dashboard: unavailable (missing $CORE_DASHBOARD_FILE)"
fi

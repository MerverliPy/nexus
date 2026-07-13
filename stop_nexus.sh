#!/bin/bash
set -e

echo "🛑 Stopping Nexus services..."

# Stop API server
if [ -f /tmp/nexus_api.pid ]; then
    API_PID=$(cat /tmp/nexus_api.pid)
    if ps -p $API_PID > /dev/null 2>&1; then
        echo "   Stopping API server (PID: $API_PID)..."
        kill $API_PID
        rm /tmp/nexus_api.pid
    else
        echo "   API server not running"
        rm /tmp/nexus_api.pid 2>/dev/null || true
    fi
else
    echo "   No API server PID file found"
fi

# Stop web UI
if [ -f /tmp/nexus_web.pid ]; then
    WEB_PID=$(cat /tmp/nexus_web.pid)
    if ps -p $WEB_PID > /dev/null 2>&1; then
        echo "   Stopping Web UI (PID: $WEB_PID)..."
        kill $WEB_PID
        rm /tmp/nexus_web.pid
    else
        echo "   Web UI not running"
        rm /tmp/nexus_web.pid 2>/dev/null || true
    fi
else
    echo "   No Web UI PID file found"
fi

# Optional: Stop Docker services
read -p "Stop Docker services (PostgreSQL/Redis/MinIO)? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    cd /home/calvin/nexus
    echo "   Stopping Docker containers..."
    docker-compose down
fi

echo ""
echo "✅ Nexus services stopped"

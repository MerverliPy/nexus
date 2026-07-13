#!/bin/bash
set -e

echo "🚀 Starting Nexus for Remote Access..."

# Navigate to project
cd /home/calvin/nexus

# Activate venv
source venv/bin/activate

# Check if Docker services are running
echo "📦 Checking Docker services..."
if ! docker ps | grep -q postgres; then
    echo "   Starting PostgreSQL..."
    # Assuming you're using existing finance-bot-db
    echo "   (Using existing PostgreSQL from finance-bot-db)"
fi

if ! docker ps | grep -q redis; then
    echo "   Starting Redis..."
    docker-compose up -d redis
fi

if ! docker ps | grep -q minio; then
    echo "   Starting MinIO..."
    docker-compose up -d minio
fi

# Wait for services
echo "   Waiting for services to be ready..."
sleep 3

# Run migrations
echo "🗄️ Running database migrations..."
alembic upgrade head

# Stop any existing API server
if [ -f /tmp/nexus_api.pid ]; then
    OLD_PID=$(cat /tmp/nexus_api.pid)
    if ps -p $OLD_PID > /dev/null 2>&1; then
        echo "🛑 Stopping existing API server (PID: $OLD_PID)..."
        kill $OLD_PID || true
        sleep 2
    fi
fi

# Start API
echo "🖥️ Starting API server on 0.0.0.0:8000..."
uvicorn src.nexus.api.main:app --host 0.0.0.0 --port 8000 --reload > /tmp/nexus_api.log 2>&1 &
echo $! > /tmp/nexus_api.pid
sleep 3

# Test API
echo "✅ Testing API..."
if curl -sf http://localhost:8000/health > /dev/null; then
    echo "   API is healthy!"
    curl -s http://localhost:8000/health | python3 -m json.tool 2>/dev/null || curl -s http://localhost:8000/health
else
    echo "   ⚠️  API health check failed. Check logs: tail -f /tmp/nexus_api.log"
fi

# Stop any existing web server
if [ -f /tmp/nexus_web.pid ]; then
    OLD_PID=$(cat /tmp/nexus_web.pid)
    if ps -p $OLD_PID > /dev/null 2>&1; then
        echo "🛑 Stopping existing web server (PID: $OLD_PID)..."
        kill $OLD_PID || true
        sleep 2
    fi
fi

# Start Web UI
echo "🌐 Starting Web UI on 0.0.0.0:3000..."
cd web

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "   Installing npm dependencies (first run)..."
    npm install
fi

npm run dev -- -H 0.0.0.0 > /tmp/nexus_web.log 2>&1 &
echo $! > /tmp/nexus_web.pid

# Get Tailscale IP
TAILSCALE_IP=$(tailscale ip -4 2>/dev/null || echo "100.81.83.98")

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Nexus is now running!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📱 Open on iPhone (via Tailscale):"
echo "   🌐 Web UI:   http://${TAILSCALE_IP}:3000"
echo "   🔌 API:      http://${TAILSCALE_IP}:8000"
echo "   📖 API Docs: http://${TAILSCALE_IP}:8000/docs"
echo ""
echo "💻 Local access:"
echo "   🌐 Web UI:   http://localhost:3000"
echo "   🔌 API:      http://localhost:8000"
echo ""
echo "📊 View logs:"
echo "   API:  tail -f /tmp/nexus_api.log"
echo "   Web:  tail -f /tmp/nexus_web.log"
echo ""
echo "🛑 Stop services:"
echo "   Run: ./stop_nexus.sh"
echo "   Or:  kill \$(cat /tmp/nexus_api.pid) && kill \$(cat /tmp/nexus_web.pid)"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

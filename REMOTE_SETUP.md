# 📱 Remote Access Setup Guide for Nexus (iPhone + Tailscale)

**Last Updated:** 2026-07-11  
**Your Tailscale IP:** `100.81.83.98`  
**Your WSL2 Hostname:** `CALVINPC`

This guide provides exact step-by-step instructions to run Nexus on your WSL2 Ubuntu machine and connect remotely from your iPhone via Tailscale.

---

## 🎯 Overview

You will:
1. ✅ Configure environment variables for remote access
2. ✅ Start Docker services (PostgreSQL, Redis, MinIO)
3. ✅ Run database migrations
4. ✅ Start the FastAPI backend server
5. ✅ Start the Next.js web UI
6. ✅ Connect from your iPhone using Safari

**Total Time:** ~10 minutes

---

## 📋 Prerequisites Checklist

Before starting, verify:

- [x] WSL2 Ubuntu is running on CALVINPC
- [x] Tailscale is active (`tailscale ip -4` shows `100.81.83.98`)
- [x] iPhone has Tailscale app installed and connected to the same network
- [x] PostgreSQL exists at `finance-bot-db` (you're reusing this)
- [x] Python 3.11+ virtual environment at `/home/calvin/nexus/venv`
- [ ] OpenAI API key available (for voice features)

---

## 🚀 Step 1: Configure Environment (3 minutes)

### 1.1 Backup Current .env (Safety First)

```bash
cd /home/calvin/nexus
cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
```

### 1.2 Update .env for Remote Access

Open `.env` in your editor:

```bash
nano .env
```

**Add/Update these critical lines:**

```bash
# ============================================================
# REMOTE ACCESS CONFIGURATION
# ============================================================

# API Server - MUST bind to 0.0.0.0 for Tailscale access
NEXUS_API_HOST=0.0.0.0
NEXUS_API_PORT=8000

# CORS - Allow iPhone to connect via Tailscale IP
NEXUS_CORS_ORIGINS=http://100.81.83.98:3000,http://100.81.83.98:8000,http://localhost:3000,http://localhost:8000

# OpenAI API Key (required for voice features)
OPENAI_API_KEY=sk-proj-...YOUR_KEY_HERE...

# Environment
NEXUS_ENV=development
NEXUS_DEBUG=true
NEXUS_LOG_LEVEL=INFO

# Database (reusing finance-bot-db)
NEXUS_DB_HOST=localhost
NEXUS_DB_PORT=5432
NEXUS_DB_NAME=nexus_db
NEXUS_DB_USER=bot
NEXUS_DB_PASSWORD=YOUR_EXISTING_PASSWORD

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Security Keys (generate if not set)
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
NEXUS_SECRET_KEY=YOUR_GENERATED_KEY_HERE
NEXUS_ENCRYPTION_KEY=YOUR_GENERATED_KEY_HERE

# MinIO (if using file uploads)
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=nexus-data
MINIO_SECURE=false
```

**Save and exit:** `Ctrl+O`, `Enter`, `Ctrl+X`

### 1.3 Generate Security Keys (if needed)

```bash
# Generate JWT secret key
python -c "import secrets; print('NEXUS_SECRET_KEY=' + secrets.token_urlsafe(32))"

# Generate encryption key
python -c "from cryptography.fernet import Fernet; print('NEXUS_ENCRYPTION_KEY=' + Fernet.generate_key().decode())"
```

Copy the output and paste into `.env`.

---

## 🐳 Step 2: Start Docker Services (2 minutes)

### 2.1 Check if PIA Stack is Running

```bash
docker ps | grep -E "postgres|redis|minio"
```

**Expected output:** Your `finance-bot-db` PostgreSQL and Redis containers.

### 2.2 Start MinIO (if not running)

```bash
cd /home/calvin/nexus
docker-compose up -d minio
```

### 2.3 Verify All Services

```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

**Expected:**
- PostgreSQL on port `5432`
- Redis on port `6379`
- MinIO on port `9000`

---

## 🗄️ Step 3: Database Setup (2 minutes)

### 3.1 Activate Virtual Environment

```bash
cd /home/calvin/nexus
source venv/bin/activate
```

**Verify:** Your prompt should show `(venv)` prefix.

### 3.2 Run Database Migrations

```bash
# Check current migration state
alembic current

# Apply all migrations
alembic upgrade head
```

**Expected output:**
```
INFO  [alembic.runtime.migration] Running upgrade -> 1a2b3c4d5e6f, initial_schema
INFO  [alembic.runtime.migration] Running upgrade 1a2b3c4d5e6f -> 2b3c4d5e6f7g, add_vendor_aliases
...
```

### 3.3 Verify Database Tables

```bash
# Connect to database
psql -h localhost -U bot -d nexus_db -c "\dt"
```

**Expected:** Tables like `users`, `tasks`, `transactions`, `notes`, etc.

---

## 🖥️ Step 4: Start FastAPI Backend (1 minute)

### 4.1 Start API Server in Background

```bash
cd /home/calvin/nexus
source venv/bin/activate

# Start API server (binds to 0.0.0.0:8000)
uvicorn src.nexus.api.main:app --host 0.0.0.0 --port 8000 --reload &

# Save the process ID
echo $! > /tmp/nexus_api.pid
```

### 4.2 Verify API is Running

```bash
# Check local
curl http://localhost:8000/health

# Check via Tailscale IP (from WSL)
curl http://100.81.83.98:8000/health
```

**Expected response:**
```json
{"status":"healthy","env":"development"}
```

### 4.3 View API Logs (Optional)

```bash
tail -f ~/.nexus/logs/nexus.log
# Or check uvicorn output in terminal
```

---

## 🌐 Step 5: Start Next.js Web UI (2 minutes)

### 5.1 Install Node Dependencies (First Time Only)

```bash
cd /home/calvin/nexus/web
npm install
```

### 5.2 Update Next.js Config for Remote Access

Open `web/next.config.js`:

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Allow connections from any host (Tailscale)
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          { key: 'Access-Control-Allow-Origin', value: '*' },
        ],
      },
    ]
  },
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://100.81.83.98:8000',
  },
}

module.exports = nextConfig
```

### 5.3 Create Environment File for Web UI

```bash
cd /home/calvin/nexus/web
cat > .env.local << 'EOF'
NEXT_PUBLIC_API_URL=http://100.81.83.98:8000
EOF
```

### 5.4 Start Next.js Dev Server

```bash
cd /home/calvin/nexus/web

# Start on port 3000, accessible from any interface
npm run dev -- -H 0.0.0.0 &

# Save the process ID
echo $! > /tmp/nexus_web.pid
```

**Expected output:**
```
ready - started server on 0.0.0.0:3000, url: http://100.81.83.98:3000
```

---

## 📱 Step 6: Connect from iPhone (1 minute)

### 6.1 Verify Tailscale on iPhone

1. Open **Tailscale app** on iPhone
2. Verify you're connected (green checkmark)
3. Note: Your iPhone can see `100.81.83.98` (CALVINPC)

### 6.2 Open Nexus in Safari

1. Open **Safari** on iPhone
2. Navigate to: **`http://100.81.83.98:3000`**
3. You should see the Nexus dashboard

### 6.3 Test API Connection

In Safari address bar, try:
```
http://100.81.83.98:8000/health
```

**Expected:** JSON response `{"status":"healthy",...}`

### 6.4 Register Your First User

1. On the Nexus web UI, click **"Sign Up"**
2. Create account:
   - Email: `calvinbrady8@gmail.com`
   - Password: (your choice)
3. Login and verify dashboard loads

---

## 🔧 Troubleshooting

### Problem: "Connection Refused" on iPhone

**Solution 1: Check Windows Firewall**
```powershell
# Run in Windows PowerShell (NOT WSL)
New-NetFirewallRule -DisplayName "Nexus API" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "Nexus Web" -Direction Inbound -LocalPort 3000 -Protocol TCP -Action Allow
```

**Solution 2: Check WSL Networking**
```bash
# In WSL, get Windows host IP
ip route show | grep -i default | awk '{print $3}'

# Test connectivity TO Windows
curl http://<windows_ip>:8000/health
```

**Solution 3: Restart WSL Networking**
```powershell
# In Windows PowerShell (as Admin)
wsl --shutdown
# Then reopen WSL terminal
```

### Problem: CORS Errors in Browser

**Solution:** Verify CORS origins in `.env`:
```bash
cd /home/calvin/nexus
grep CORS .env
# Should show: NEXUS_CORS_ORIGINS=http://100.81.83.98:3000,http://100.81.83.98:8000
```

Restart API server after changing:
```bash
kill $(cat /tmp/nexus_api.pid)
uvicorn src.nexus.api.main:app --host 0.0.0.0 --port 8000 --reload &
echo $! > /tmp/nexus_api.pid
```

### Problem: Database Connection Failed

**Check PostgreSQL is running:**
```bash
docker ps | grep postgres
psql -h localhost -U bot -d nexus_db -c "SELECT 1"
```

**Check credentials in .env:**
```bash
grep "NEXUS_DB_" /home/calvin/nexus/.env
```

### Problem: "Module not found" errors

**Reinstall dependencies:**
```bash
cd /home/calvin/nexus
source venv/bin/activate
pip install -e .
```

---

## 🛑 Stopping Services

### Stop All Services Gracefully

```bash
# Stop API server
kill $(cat /tmp/nexus_api.pid 2>/dev/null)

# Stop web UI
kill $(cat /tmp/nexus_web.pid 2>/dev/null)

# Stop Docker services (optional)
cd /home/calvin/nexus
docker-compose down
```

---

## 🚀 Quick Start Script (All-in-One)

Save this as `start_nexus_remote.sh`:

```bash
#!/bin/bash
set -e

echo "🚀 Starting Nexus for Remote Access..."

# Navigate to project
cd /home/calvin/nexus

# Activate venv
source venv/bin/activate

# Start Docker services
echo "📦 Starting Docker services..."
docker-compose up -d

# Wait for services
sleep 5

# Run migrations
echo "🗄️ Running database migrations..."
alembic upgrade head

# Start API
echo "🖥️ Starting API server..."
uvicorn src.nexus.api.main:app --host 0.0.0.0 --port 8000 --reload > /tmp/nexus_api.log 2>&1 &
echo $! > /tmp/nexus_api.pid
sleep 3

# Test API
echo "✅ Testing API..."
curl -s http://100.81.83.98:8000/health | jq '.'

# Start Web UI
echo "🌐 Starting Web UI..."
cd web
npm run dev -- -H 0.0.0.0 > /tmp/nexus_web.log 2>&1 &
echo $! > /tmp/nexus_web.pid

echo ""
echo "✅ Nexus is now running!"
echo "📱 Open on iPhone: http://100.81.83.98:3000"
echo "🔌 API endpoint: http://100.81.83.98:8000"
echo ""
echo "📊 View logs:"
echo "   API:  tail -f /tmp/nexus_api.log"
echo "   Web:  tail -f /tmp/nexus_web.log"
echo ""
echo "🛑 Stop services: ./stop_nexus.sh"
```

Make it executable:
```bash
chmod +x start_nexus_remote.sh
```

Run it:
```bash
./start_nexus_remote.sh
```

---

## 📊 System Status Commands

### Check What's Running

```bash
# Check API
curl http://100.81.83.98:8000/health

# Check Web UI
curl -I http://100.81.83.98:3000

# Check Docker services
docker-compose ps

# Check processes
ps aux | grep -E "uvicorn|next"
```

### View Logs

```bash
# API logs
tail -f /tmp/nexus_api.log

# Web UI logs
tail -f /tmp/nexus_web.log

# Docker logs
docker-compose logs -f
```

---

## 🔐 Security Notes

1. **Tailscale Firewall**: Your Nexus is only accessible via your private Tailscale network. External internet cannot reach it.

2. **API Keys**: Never commit `.env` to git. Your OpenAI key and database password are sensitive.

3. **HTTPS**: For production, use a reverse proxy (nginx/Caddy) with Let's Encrypt SSL.

4. **MFA**: Enable TOTP two-factor authentication after first login (see `docs/OPERATIONS.md`).

---

## 📚 Next Steps

After successful connection:

1. ✅ **Create your first task**: `nexus task add "Review documentation"`
2. ✅ **Upload a receipt**: Try the OCR feature in Finance tab
3. ✅ **Create a note**: Use the Research tab for knowledge management
4. ✅ **Enable voice features**: Configure OpenAI API key and try voice commands
5. ✅ **Set up recurring tasks**: Create daily/weekly reminders

---

## 🆘 Getting Help

- **Documentation**: `/home/calvin/nexus/README.md`
- **API Reference**: `http://100.81.83.98:8000/docs` (Interactive Swagger UI)
- **Test Suite**: `pytest` (163 passing tests)
- **Issues**: File bugs in the GitHub repo

---

**Your Nexus Tailscale Endpoints:**

- 🌐 **Web UI**: `http://100.81.83.98:3000`
- 🔌 **API**: `http://100.81.83.98:8000`
- 📊 **API Docs**: `http://100.81.83.98:8000/docs`
- 🏥 **Health Check**: `http://100.81.83.98:8000/health`

**Happy automating! 🎉**

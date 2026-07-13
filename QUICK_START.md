# Nexus Remote Access - Quick Reference Card

## 🚀 One-Command Start

```bash
cd /home/calvin/nexus
./start_nexus_remote.sh
```

## 🛑 One-Command Stop

```bash
cd /home/calvin/nexus
./stop_nexus.sh
```

---

## 📱 Your iPhone URLs (via Tailscale)

| Service | URL | Purpose |
|---------|-----|---------|
| **Web UI** | `http://100.81.83.98:3000` | Main dashboard |
| **API** | `http://100.81.83.98:8000` | Backend API |
| **API Docs** | `http://100.81.83.98:8000/docs` | Interactive Swagger UI |
| **Health Check** | `http://100.81.83.98:8000/health` | Status endpoint |

---

## 🔧 Manual Control Commands

### Check Status
```bash
# API health
curl http://100.81.83.98:8000/health

# Check running processes
ps aux | grep -E "uvicorn|next-server"

# Check Docker services
docker ps | grep -E "postgres|redis|minio"
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

### Restart Services
```bash
# Restart API only
kill $(cat /tmp/nexus_api.pid)
cd /home/calvin/nexus && source venv/bin/activate
uvicorn src.nexus.api.main:app --host 0.0.0.0 --port 8000 --reload &
echo $! > /tmp/nexus_api.pid

# Restart Web UI only
kill $(cat /tmp/nexus_web.pid)
cd /home/calvin/nexus/web
npm run dev -- -H 0.0.0.0 &
echo $! > /tmp/nexus_web.pid
```

---

## 🐛 Troubleshooting One-Liners

### Can't connect from iPhone?
```bash
# Check Tailscale IP
tailscale ip -4

# Test from WSL
curl http://100.81.83.98:8000/health

# Check Windows Firewall (run in PowerShell)
New-NetFirewallRule -DisplayName "Nexus" -Direction Inbound -LocalPort 8000,3000 -Protocol TCP -Action Allow
```

### Database errors?
```bash
# Check PostgreSQL
docker ps | grep postgres
psql -h localhost -U bot -d nexus_db -c "SELECT 1"

# Run migrations
cd /home/calvin/nexus && source venv/bin/activate
alembic upgrade head
```

### CORS errors in browser?
```bash
# Check CORS config
grep CORS /home/calvin/nexus/.env

# Should contain: NEXUS_CORS_ORIGINS=http://100.81.83.98:3000,http://100.81.83.98:8000
```

---

## 📊 System Requirements Met

- ✅ WSL2 Ubuntu on CALVINPC
- ✅ Tailscale IP: `100.81.83.98`
- ✅ Python 3.11+ with venv
- ✅ PostgreSQL (finance-bot-db)
- ✅ Redis
- ✅ Node.js 18+
- ✅ 163 passing tests

---

## 🔐 Security Checklist

- ✅ API binds to `0.0.0.0` (required for Tailscale)
- ✅ Access limited to Tailscale network only
- ✅ Database password set in `.env`
- ✅ OpenAI API key in `.env`
- ✅ JWT secret keys generated
- ⚠️ HTTPS not configured (Tailscale encrypts traffic)

---

## 📚 Full Documentation

- **Setup Guide**: `/home/calvin/nexus/REMOTE_SETUP.md`
- **API Reference**: `http://100.81.83.98:8000/docs` (after starting)
- **Feature Docs**: `/home/calvin/nexus/README.md`
- **Contributing**: `/home/calvin/nexus/CONTRIBUTING.md`

---

**Last Updated:** 2026-07-11  
**Your Nexus Version:** 1.0 (All 5 phases complete)

# 🚀 Nexus Quick Start Guide

**Goal:** Get Nexus running locally in under 10 minutes.

---

## 📦 Prerequisites

Before starting, ensure you have:

- **Python 3.11+** - [Download](https://www.python.org/downloads/)
- **Docker & Docker Compose** - [Install Docker](https://docs.docker.com/get-docker/)
- **PostgreSQL client tools** (optional, for manual DB access) - `sudo apt install postgresql-client`
- **OpenRouter API key** (or compatible LLM provider) - [Get API key](https://openrouter.ai/keys)

**System Requirements:**
- 4 GB RAM minimum (8 GB recommended)
- 2 CPU cores
- 5 GB disk space for Docker images + data

## Installation

### 1. Clone and setup

```bash
cd ~/nexus
./scripts/setup.sh
```

This will:
- Create a Python virtual environment
- Install dependencies
- Copy `.env.example` to `.env`
- Start Docker services (PostgreSQL, Redis, MinIO, Prometheus, Grafana)
- Run database migrations
- Prompt you to create an admin account

### 2. Configure environment

Edit `.env` and set your credentials:

```bash
nano .env
```

Key variables to configure:
- `NEXUS_ENCRYPTION_KEY` — Generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- `NEXUS_JWT_SECRET_KEY` — Generate with: `openssl rand -hex 32`
- `OPENROUTER_API_KEY` — From https://openrouter.ai/keys
- `NEXUS_DB_PASSWORD` — Change from default

### 3. Start services

#### Backend API
```bash
source venv/bin/activate
uvicorn nexus.api.main:app --host 0.0.0.0 --port 8000 --reload
```

#### Background workers (Celery)
```bash
celery -A nexus.workers.app worker --loglevel=info
```

#### Task scheduler (Celery Beat)
```bash
celery -A nexus.workers.app beat --loglevel=info
```

## ✅ Verify Installation

After setup completes, verify all services are running:

```bash
# Check Docker containers (should see 6 services: postgres, redis, minio, prometheus, grafana, and beat)
docker-compose ps

# All services should show "Up" status. If any show "Exit" or "Restarting":
docker-compose logs <service-name>  # e.g., docker-compose logs postgres

# Test database connectivity
psql -h localhost -U nexus_user -d nexus_db -c "SELECT version();"
# Password is in your .env file (NEXUS_DB_PASSWORD)

# Test API health
curl http://localhost:8000/health
# Should return: {"status": "healthy", "version": "0.1.0"}
```

**Expected Output:**
- ✅ 6 Docker containers running
- ✅ PostgreSQL accepts connections
- ✅ API returns health check response

---

## 🎯 First Steps

### CLI

```bash
# Activate virtual environment
source venv/bin/activate

# Task management
nexus task add "Review project proposal" --due tomorrow --priority 1
nexus task list --status pending

# Finance
nexus finance log 42.50 "Whole Foods" --category groceries
nexus finance list --month 2026-07

# Knowledge base
nexus note create "Meeting notes: Product roadmap"
nexus note search "machine learning papers"

# System status
nexus status
```

### API

Access the interactive API documentation:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

### Monitoring

- **Grafana dashboards:** http://localhost:3001 (admin/admin)
- **Prometheus metrics:** http://localhost:9090
- **MinIO console:** http://localhost:9001 (minioadmin/minioadmin)

## Development Workflow

### Database migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "Add user preferences table"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

### Running tests

```bash
pytest tests/ -v --cov=nexus
```

### Code quality

```bash
# Format
black src/ tests/

# Lint
ruff check src/ tests/

# Type check
mypy src/
```

## Architecture Overview

```
nexus/
├── src/nexus/
│   ├── api/           # FastAPI routes and middleware
│   ├── models/        # SQLAlchemy ORM models
│   ├── services/      # Business logic layer
│   ├── workers/       # Celery background tasks
│   ├── cli/           # CLI commands
│   └── utils/         # Shared utilities
├── migrations/        # Alembic database migrations
├── tests/            # Pytest test suite
├── scripts/          # Setup and maintenance scripts
├── config/           # Prometheus, Grafana configs
└── docker-compose.yml
```

## Next Steps

1. **Configure MFA/TOTP** — Follow `docs/OPERATIONS.md` section 1.2
2. **Set up backups** — Follow `docs/OPERATIONS.md` section 3
3. **Enable OpenTelemetry** — Follow `docs/OPERATIONS.md` section 4.3
4. **Review security checklist** — `docs/OPERATIONS.md` section 1

## 🔧 Troubleshooting

### Common Issues & Solutions

#### 🚨 Database connection errors

**Symptoms:** `sqlalchemy.exc.OperationalError` or "connection refused"

```bash
# 1. Check if PostgreSQL container is running
docker-compose ps postgres

# 2. If not running, check logs
docker-compose logs postgres

# 3. Restart PostgreSQL
docker-compose restart postgres

# 4. Verify connectivity
docker exec -it nexus-postgres-1 psql -U nexus_user -d nexus_db -c "SELECT 1;"
```

**Common Causes:**
- Port 5432 already in use (another PostgreSQL instance running)
- Insufficient memory allocated to Docker
- Database initialization failed (check logs for disk space issues)

---

#### 🚨 Migration failures

**Symptoms:** `alembic.util.exc.CommandError` or "target database is not up to date"

```bash
# Check current migration status
alembic current

# View migration history
alembic history

# Reset database (⚠️ DESTROYS ALL DATA - development only)
docker-compose down -v
docker-compose up -d
sleep 10
alembic upgrade head
```

**Common Causes:**
- Migration was partially applied before failure
- Database schema manually modified outside of Alembic
- Downgraded without running proper `alembic downgrade` command

---

#### 🚨 Worker not processing tasks

**Symptoms:** Tasks stuck in "pending" status, no activity in worker logs

```bash
# 1. Check Redis connectivity
docker-compose ps redis
redis-cli -h localhost -p 6379 ping
# Should return: PONG

# 2. Inspect active tasks
celery -A nexus.workers.app inspect active

# 3. Restart worker
# Find the worker process (usually terminal session running it)
# Press Ctrl+C and restart:
celery -A nexus.workers.app worker --loglevel=info

# 4. Check for stuck tasks in Redis
redis-cli -h localhost -p 6379 KEYS "celery*"
```

**Common Causes:**
- Worker not started (forgot to run in separate terminal)
- Redis connection lost
- Task timeout exceeded (check task implementation)

---

#### 🚨 Port already in use

**Symptoms:** `OSError: [Errno 48] Address already in use`

```bash
# Find process using port 8000 (or whatever port is conflicting)
lsof -i :8000

# Kill the process
kill -9 <PID>

# Or use a different port
uvicorn nexus.api.main:app --port 8001
```

---

### 🆘 Still Stuck?

If none of the above resolves your issue:

1. **Check full logs**: `docker-compose logs --tail=100 --follow`
2. **Review environment**: `cat .env` (ensure all required variables are set)
3. **Verify Python version**: `python --version` (must be 3.11+)
4. **Check disk space**: `df -h` (ensure adequate space for Docker volumes)
5. **Open an issue**: [GitHub Issues](https://github.com/calvin/nexus/issues) with:
   - Full error message
   - Output of `docker-compose ps`
   - Operating system and version
   - Steps to reproduce

---

## 📚 Next Steps & Learning Resources

After getting Nexus running, explore these resources:

1. **📖 [SPECIFICATION.md](SPECIFICATION.md)** - Complete system architecture and design decisions
2. **🗺️ [ROADMAP.md](ROADMAP.md)** - 20-week implementation timeline (see what's coming)
3. **🔒 [docs/OPERATIONS.md](docs/OPERATIONS.md)** - Security hardening, backups, and monitoring setup
4. **🤝 [CONTRIBUTING.md](CONTRIBUTING.md)** - Contributing guidelines if you want to improve Nexus
5. **📊 API Documentation** - Interactive docs at http://localhost:8000/docs (Swagger UI)

### Recommended Configuration

- **Enable MFA** - Follow `docs/OPERATIONS.md` section 1.2 for TOTP setup
- **Set up automated backups** - Follow `docs/OPERATIONS.md` section 3
- **Configure monitoring** - Grafana dashboards at http://localhost:3001 (admin/admin)
- **Review security checklist** - `docs/OPERATIONS.md` section 1

---

## 📞 Support

- **Documentation:** See `SPECIFICATION.md`, `ROADMAP.md`, and `docs/OPERATIONS.md`
- **Issues:** Check logs in `logs/` directory or Docker Compose logs
- **Configuration:** Review `.env` and `src/nexus/config.py`
- **Community:** Open a [GitHub Issue](https://github.com/calvin/nexus/issues) or [Discussion](https://github.com/calvin/nexus/discussions)

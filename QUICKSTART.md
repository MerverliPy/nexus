# Nexus Quick Start Guide

## Prerequisites

- **Python 3.11+**
- **Docker & Docker Compose**
- **PostgreSQL client tools** (optional, for manual DB access)
- **OpenRouter API key** (or compatible LLM provider)

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

## Usage

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

## Troubleshooting

### Database connection errors
```bash
# Check PostgreSQL is running
docker-compose ps postgres

# View logs
docker-compose logs postgres

# Restart services
docker-compose restart postgres
```

### Migration failures
```bash
# Reset database (⚠️ DESTROYS DATA)
docker-compose down -v
docker-compose up -d
alembic upgrade head
```

### Worker not processing tasks
```bash
# Check Redis connectivity
docker-compose ps redis
redis-cli -h localhost -p 6379 ping

# View worker logs
celery -A nexus.workers.app inspect active
```

## Support

- **Documentation:** See `SPECIFICATION.md`, `ROADMAP.md`, and `docs/OPERATIONS.md`
- **Issues:** Check logs in `logs/` directory
- **Configuration:** Review `.env` and `src/nexus/config.py`

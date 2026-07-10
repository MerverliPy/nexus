# Nexus Personal AI System

[![CI](https://github.com/MerverliPy/nexus/actions/workflows/ci.yml/badge.svg)](https://github.com/MerverliPy/nexus/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

**Your autonomous intelligence platform for tasks, finance, and research.**

## Overview

Nexus is a self-hosted, privacy-first AI assistant that helps you manage:

- **📋 Tasks & Calendar** - Smart scheduling, recurring tasks, natural language input
- **💰 Financial Intelligence** - Transaction tracking, receipt OCR, budget forecasting, investment analysis
- **📚 Research & Knowledge** - Personal wiki with semantic search, automated research workflows, academic paper discovery

**Key Features:**
- ✅ Self-hosted (complete data sovereignty)
- ✅ Multi-interface (CLI, Web, SMS, Email, Voice)
- ✅ Learning system (improves from your corrections)
- ✅ Proactive intelligence (monitors, alerts, suggests)
- ✅ Production-grade (MFA, encryption, backups, monitoring)

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 16+ with pgvector
- Redis 7.2+
- MinIO (or S3-compatible storage)

### Installation

```bash
# Clone repository
git clone https://github.com/calvin/nexus.git
cd nexus

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Setup environment variables
cp .env.example .env
# Edit .env with your credentials

# Start infrastructure (PostgreSQL, Redis, MinIO)
docker-compose up -d

# Run database migrations
alembic upgrade head

# Start backend
uvicorn nexus.api.main:app --reload

# Start worker
celery -A nexus.workers.app worker --loglevel=info
```

### First Steps

```bash
# Register user
nexus auth register --email you@example.com --password <password>

# Login
nexus auth login

# Create your first task
nexus task add "Review Nexus documentation" --due tomorrow

# Log an expense
nexus finance log 50 "Coffee" --category Dining

# Start a research project
nexus research "Compare investment strategies"
```

## Project Structure

```
nexus/
├── src/nexus/          # Main application code
│   ├── api/            # FastAPI routers
│   ├── models/         # SQLAlchemy models
│   ├── services/       # Business logic
│   ├── workers/        # Celery tasks
│   ├── cli/            # Click CLI commands
│   └── utils/          # Helpers & utilities
├── tests/              # Test suite
├── docs/               # Documentation
├── scripts/            # Operational scripts
├── config/             # Configuration files
├── migrations/         # Alembic migrations
└── docker-compose.yml  # Infrastructure
```

## Documentation

- [Technical Specification](SPECIFICATION.md) - Complete system architecture
- [Implementation Roadmap](ROADMAP.md) - 20-week development plan
- [Operations Guide](docs/OPERATIONS.md) - Security, backups, monitoring

## Development

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=nexus --cov-report=html

# Specific test file
pytest tests/test_tasks.py
```

### Code Quality

```bash
# Type checking
mypy src/

# Linting
ruff check src/

# Formatting
black src/
```

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## Architecture

```
┌─────────────┐
│  CLI / Web  │
└──────┬──────┘
       │
┌──────▼──────┐
│   FastAPI   │
└──────┬──────┘
       │
   ┌───┴───┐
   │       │
┌──▼──┐ ┌──▼───┐
│ DB  │ │Worker│
└─────┘ └──────┘
```

**Tech Stack:**
- Backend: FastAPI (Python)
- Database: PostgreSQL + pgvector
- Queue: Celery + Redis
- Storage: MinIO (S3)
- Frontend: Next.js + shadcn/ui
- CLI: Click + Rich

## Security

- 🔐 Multi-factor authentication (TOTP)
- 🔒 Field-level encryption for sensitive data
- 📝 Comprehensive audit logging
- 🔑 Secure credential storage
- 🛡️ Rate limiting & circuit breakers

See [Operations Guide](docs/OPERATIONS.md) for security hardening procedures.

## Roadmap

**Phase 1 (Weeks 1-4):** Infrastructure & Task Management ✅  
**Phase 2 (Weeks 5-8):** Financial Intelligence Core  
**Phase 3 (Weeks 9-12):** Security & Production Hardening  
**Phase 4 (Weeks 13-16):** Research & Knowledge Management  
**Phase 5 (Weeks 17-20):** Advanced Features (Voice, Mobile, Portfolio)

See [ROADMAP.md](ROADMAP.md) for detailed timeline.

## Contributing

Nexus is a personal project, but contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) for details.

## Support

- 📧 Email: calvinbrady8@gmail.com
- 🐛 Issues: [GitHub Issues](https://github.com/calvin/nexus/issues)
- 📖 Docs: [Documentation](docs/)

---

**Built with ❤️ for personal productivity and privacy.**

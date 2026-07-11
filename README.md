# Nexus Personal AI System

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

> **Your autonomous intelligence platform for tasks, finance, and research.**

Nexus is a self-hosted AI assistant that unifies task management, financial tracking, and research workflows into a single, privacy-first system. Built for technical users who value data sovereignty and production-grade reliability.

> 🚀 **New to Nexus?** Start with the [**30-Minute Getting Started Guide**](GETTING_STARTED.md) to go from zero to your first working task.

---

## ✨ Key Features at a Glance

### 📋 Intelligent Task Management
- Natural language task creation ("Remind me to review the budget next Tuesday")
- Smart scheduling with conflict detection
- Recurring tasks with flexible patterns (daily, weekly, custom cron)
- Priority-based auto-scheduling

### 💰 Financial Intelligence
- Receipt OCR with automatic categorization (ML-powered)
- Multi-account transaction tracking
- Budget forecasts and spending alerts
- Investment portfolio analysis (coming soon)

### 📚 Research & Knowledge Base
- Personal wiki with semantic search (pgvector)
- Automated research workflows
- Academic paper discovery (arXiv integration)
- Cross-reference linking between notes

### 🔒 Security & Privacy
- Self-hosted (complete data sovereignty)
- Multi-factor authentication (TOTP)
- Field-level encryption for sensitive data
- Comprehensive audit logging

### 🌐 Multi-Interface Access
- **CLI** - Primary interface with rich formatting
- **Web Dashboard** - Real-time updates via WebSocket
- **API** - RESTful API with interactive docs
- **SMS/Email** - Remote task creation (optional)
- **Voice** - Voice interface (planned Phase 5)

---

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

## ⚡ Quick Start

Get Nexus running in under 5 minutes with the automated setup script.

### Prerequisites

Ensure you have these installed:

- **Python 3.11+** - [Download](https://www.python.org/downloads/)
- **Docker & Docker Compose** - [Install Docker](https://docs.docker.com/get-docker/)
- **Git** - For cloning the repository

> **Note:** The setup script will automatically provision PostgreSQL 16 (with pgvector), Redis 7.2, and MinIO via Docker Compose.

### Installation

```bash
# Clone the repository
git clone https://github.com/calvin/nexus.git
cd nexus

# Run automated setup (creates venv, installs deps, starts services)
./scripts/setup.sh

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

## 📞 Support & Community

For questions, bug reports, or feature requests:

- 📖 **[Getting Started Guide](GETTING_STARTED.md)** - 30-minute tutorial from zero to running
- 🔍 **[FAQ](docs/FAQ.md)** - 40+ common questions answered
- 📊 **[Feature Comparison](docs/COMPARISON.md)** - Compare Nexus vs commercial alternatives
- 📖 **[Documentation](docs/)** - Check `SPECIFICATION.md`, `QUICKSTART.md`, and `OPERATIONS.md`
- 🔒 **[Security Policy](SECURITY.md)** - Vulnerability disclosure and security best practices
- 💬 **Discussions** - Open a [GitHub Discussion](https://github.com/calvin/nexus/discussions) for general questions
- 🐛 **Bug Reports** - Use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.md)
- ✨ **Feature Requests** - Use the [feature request template](.github/ISSUE_TEMPLATE/feature_request.md)
- 📧 **Private Contact** - Email: calvinbrady8@gmail.com

> **Note:** This is a personal project maintained during free time. Response times may vary, but all issues and PRs are reviewed.

---

**Built with ❤️ for personal productivity and privacy.**

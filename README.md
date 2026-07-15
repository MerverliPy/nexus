# Nexus Personal AI System

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Tests: 162 passing](https://img.shields.io/badge/tests-162%20passing-brightgreen.svg)](tests/)

> **Your autonomous intelligence platform for tasks, finance, and research — self-hosted, privacy-first, production-ready.**

Nexus is a comprehensive AI assistant that unifies **task management**, **financial intelligence**, and **research workflows** into a single, privacy-first system. Built for technical users who value data sovereignty, production-grade reliability, and extensibility.

**Status: All 5 phases complete ✅ | 162 tests passing + 1 skipped | 60% coverage**

---

## ✨ What Makes Nexus Different

- **🔒 Privacy-First** — Self-hosted, zero telemetry, end-to-end encrypted sensitive fields
- **🧠 Learning System** — ML categorization improves from corrections, tracks accuracy
- **⚡ Production-Grade** — MFA, audit logs, Prometheus metrics, circuit breakers, automated backups
- **🎯 Multi-Interface** — CLI, Web PWA, REST API, SMS gateway, voice I/O
- **📊 Intelligent** — Budget forecasting, conflict detection, semantic search, multi-source synthesis

---

## 🚀 Quick Start

Get Nexus running in **5 minutes**:

### Prerequisites

- **Python 3.11+** — [Download](https://www.python.org/downloads/)
- **Docker & Docker Compose** — [Install Docker](https://docs.docker.com/get-docker/)
- **Git** — For cloning the repository

### Installation

```bash
# Clone and enter
git clone https://github.com/calvin/nexus.git
cd nexus

# Setup virtual environment
python3.11 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Edit .env with your credentials (see Configuration section)

# Start infrastructure (PostgreSQL + pgvector, Redis, MinIO)
docker-compose up -d

# Run migrations
alembic upgrade head

# Start API server (terminal 1)
uvicorn nexus.api.main:app --host 0.0.0.0 --port 8000

# Start Celery worker (terminal 2)
celery -A nexus.workers.app worker --loglevel=info

# Start Celery beat scheduler (terminal 3)
celery -A nexus.workers.app beat --loglevel=info

# Start Next.js web dashboard (terminal 4, optional)
cd web && npm install && npm run dev
```

### First Commands

```bash
# Register and login
nexus auth register --email you@example.com --password <password>
nexus auth login

# Create a task with smart scheduling
nexus task add "Review budget" --due "tomorrow 3pm"

# Check for scheduling conflicts
nexus task suggest-slot --date tomorrow

# Log a transaction
nexus finance log 50 "Coffee" --category Dining

# Query balance and recent transactions
nexus finance balance
nexus finance recent --limit 5

# Run budget forecast
nexus finance forecast --months 3

# Create a research note
nexus note add "Investment Strategy" --content "Compare index funds vs ETFs" --tags finance,research

# Search notes semantically
nexus note search "investment options"

# Synthesize multiple research sources
nexus research synthesize --note-ids 1,2,3 --save

# Voice input (requires OpenAI API key)
nexus voice record
nexus voice speak "Your task is ready"

# SMS gateway (requires Twilio)
# Text "50 coffee" to your Twilio number → logs transaction
```

---

## 📋 Features by Domain

### Task Management (Phase 1 ✅)

| Feature | Status | Description |
|---------|--------|-------------|
| **CLI Task CRUD** | ✅ | Create, list, update, complete, delete tasks via CLI |
| **Web Dashboard** | ✅ | Next.js + shadcn/ui with real-time WebSocket updates |
| **Recurring Tasks** | ✅ | RRULE format, Celery beat scheduler, hourly generation |
| **Smart Scheduling** | ✅ | NL date parsing ("tomorrow 3pm"), conflict detection, free slot suggestions |
| **Task Dependencies** | ✅ | Dependency graph utility (`dependencies.py`) |

**API Endpoints:**  
`GET /tasks`, `POST /tasks`, `GET /tasks/{id}`, `PATCH /tasks/{id}`, `DELETE /tasks/{id}`, `GET /tasks/suggest-time`, `GET /tasks/{id}/conflicts`, `GET /tasks/suggest-slot`

**CLI Commands:**  
`nexus task add/list/complete/delete`, `nexus task parse-date`, `nexus task suggest-slot`

---

### Financial Intelligence (Phase 2 ✅)

| Feature | Status | Description |
|---------|--------|-------------|
| **Transaction CRUD** | ✅ | Multi-account tracking with encrypted notes |
| **CSV Import** | ✅ | Bank statement import with validation |
| **Receipt OCR** | ✅ | Tesseract + ML categorization with 86% test coverage |
| **ML Categorization** | ✅ | Rule-based + LLM fallback, learns from corrections |
| **Accuracy Tracking** | ✅ | Logs predictions, computes precision/recall per category |
| **Vendor Normalization** | ✅ | Fuzzy matching (>80% threshold) for consistent vendor names |
| **Budget Forecasting** | ✅ | Per-category moving average with confidence intervals |
| **Analytics** | ✅ | Spending by category/vendor, balance tracking |

**API Endpoints:**  
`GET /finance/transactions`, `POST /finance/transactions`, `POST /finance/import`, `GET /finance/analytics/spending`, `GET /finance/analytics/forecast`, `GET /finance/analytics/categorizer-accuracy`, `GET /vendors`, `POST /vendors/merge`

**CLI Commands:**  
`nexus finance log/list/balance/recent`, `nexus finance import`, `nexus finance forecast`, `nexus finance vendors`, `nexus finance merge-vendor`

---

### Security & Production (Phase 3 ✅)

| Feature | Status | Description |
|---------|--------|-------------|
| **MFA (TOTP)** | ✅ | Encrypted secret storage, QR code generation, backup codes |
| **Field Encryption** | ✅ | AES encryption for sensitive fields (notes, MFA secrets, SMS) |
| **Audit Logging** | ✅ | Tracks all auth, finance, task, research operations with IP/user-agent |
| **Session Management** | ✅ | JWT with refresh tokens, session invalidation, `refresh_sessions` Celery task |
| **Prometheus Metrics** | ✅ | `/metrics` endpoint, request latency, LLM usage tracking |
| **Backup Scripts** | ✅ | Automated DB + MinIO backup with retention policy |
| **Systemd Templates** | ✅ | Service files for API, worker, beat scheduler |
| **Circuit Breakers** | ✅ | Resilience patterns for external services (OpenAI, Twilio, Tesseract) |
| **LLM Cost Tracking** | ✅ | `LLMUsage` model tracks provider, model, tokens, cost per request |

**API Endpoints:**  
`POST /auth/register`, `POST /auth/login`, `POST /auth/mfa/setup`, `POST /auth/mfa/verify`, `POST /auth/refresh`, `GET /audit/logs`, `GET /metrics`

**CLI Commands:**  
`nexus auth register/login/mfa-setup/mfa-verify`, `nexus audit logs`

---

### Research & Knowledge (Phase 4 ✅)

| Feature | Status | Description |
|---------|--------|-------------|
| **Note CRUD** | ✅ | Markdown notes with tags, credibility scoring |
| **Wiki-Links** | ✅ | `[[Note Title]]` syntax with bidirectional link tracking |
| **Semantic Search** | ✅ | pgvector embeddings (OpenAI `text-embedding-3-small`) + FTS5 hybrid |
| **arXiv Integration** | ✅ | Search and import academic papers by query/ID |
| **Research Plans** | ✅ | LLM-generated research plans with deliverables and milestones |
| **Export Formats** | ✅ | Markdown, JSON, PDF (via pandoc) |
| **Git Versioning** | ✅ | Auto-commit on note create/update, history, restore |
| **Multi-Source Synthesis** | ✅ | Credibility-weighted LLM synthesis from 2+ notes → findings, contradictions, insights |

**API Endpoints:**  
`GET /notes`, `POST /notes`, `GET /notes/{id}`, `PATCH /notes/{id}`, `DELETE /notes/{id}`, `GET /notes/search`, `GET /notes/{id}/history`, `POST /notes/{id}/restore`, `POST /research/arxiv`, `POST /research/plan`, `POST /research/synthesize`

**CLI Commands:**  
`nexus note add/list/search/export`, `nexus note history`, `nexus note restore`, `nexus research arxiv`, `nexus research plan`

---

### Advanced Features (Phase 5 ✅)

| Feature | Status | Description |
|---------|--------|-------------|
| **Voice Input** | ✅ | OpenAI Whisper transcription + regex/LLM intent parsing |
| **Voice Output** | ✅ | OpenAI TTS-1 (6 voices: alloy/echo/fable/onyx/nova/shimmer) |
| **SMS Gateway** | ✅ | Twilio webhook with HMAC signature validation, rate limiting (10/h) |
| **Mobile PWA** | ✅ | Manifest, icons, viewport meta, fixed bottom nav, safe-area utilities |
| **Notifications** | ✅ | Email/SMS delivery for tasks, finance alerts |
| **Portfolio Tracking** | 🟡 | Asset CRUD, market data API (implementation 73% coverage) |

**SMS Commands:**  
- `50 coffee` → Log transaction  
- `balance` → Account balance  
- `recent` → Last 5 transactions  
- `remind me to X` → Create task

**API Endpoints:**  
`POST /voice/transcribe`, `POST /voice/speak`, `POST /sms/webhook`, `GET /notifications`, `POST /notifications`, `GET /portfolio/assets`

**CLI Commands:**  
`nexus voice record/parse/speak`, `nexus notify send`

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Interfaces                           │
│  CLI (Click+Rich)  │  Web (Next.js)  │  SMS  │  Voice      │
└─────────────────────────────────────────────────────────────┘
                              │
            ┌─────────────────┼─────────────────┐
            │                 │                 │
      ┌─────▼─────┐    ┌──────▼──────┐   ┌─────▼─────┐
      │  FastAPI  │◄───┤  WebSocket  │   │   Twilio  │
      │  Routers  │    │   Manager   │   │  Webhook  │
      └─────┬─────┘    └─────────────┘   └───────────┘
            │
      ┌─────▼─────────────────────────────────────┐
      │           Service Layer                   │
      │  (Business Logic, ML, Orchestration)      │
      └─────┬─────────────────────────────────────┘
            │
    ┌───────┼───────────────────┬─────────────┐
    │       │                   │             │
┌───▼───┐ ┌─▼──────┐ ┌─────────▼─────┐ ┌────▼────┐
│  DB   │ │ Redis  │ │ Celery Workers│ │  MinIO  │
│  PG   │ │ Cache  │ │   (Tasks)     │ │ (S3 API)│
│+vector│ │ Queue  │ │   Beat        │ │         │
└───────┘ └────────┘ └───────────────┘ └─────────┘
```

**Tech Stack:**

| Layer | Technology |
|-------|-----------|
| **Backend** | FastAPI 0.104+, Python 3.11+ |
| **Database** | PostgreSQL 16 + pgvector 0.7 |
| **Queue** | Celery 5.3 + Redis 7.2 |
| **Storage** | MinIO (S3-compatible) |
| **Frontend** | Next.js 14 + shadcn/ui |
| **CLI** | Click 8.1 + Rich 13.7 |
| **ML/AI** | OpenAI API (Whisper, TTS, embeddings, GPT-4), scikit-learn 1.5 |
| **OCR** | Tesseract 5+ |
| **Monitoring** | Prometheus `/metrics` endpoint |

---

## 📂 Project Structure

```
nexus/
├── src/nexus/                 # Main application
│   ├── api/                   # FastAPI application
│   │   ├── main.py           # App factory, CORS, middleware
│   │   ├── routers/          # Route handlers
│   │   │   ├── auth.py       # Auth endpoints (register, login, MFA)
│   │   │   ├── tasks.py      # Task CRUD + smart scheduling
│   │   │   ├── finance.py    # Transactions, OCR, forecasting, vendors
│   │   │   ├── research.py   # Notes, search, arXiv, synthesis
│   │   │   ├── voice.py      # Whisper transcription, TTS
│   │   │   ├── sms.py        # Twilio webhook handler
│   │   │   ├── notifications.py
│   │   │   ├── portfolio.py
│   │   │   ├── audit.py      # Audit log queries
│   │   │   └── ws.py         # WebSocket connections
│   │   └── ws_manager.py     # WebSocket broadcast manager
│   ├── models/               # SQLAlchemy ORM models
│   │   ├── user.py           # User, encrypted MFA/SMS fields
│   │   ├── task.py           # Task with recurrence
│   │   ├── finance.py        # Transaction, VendorAlias, encrypted notes
│   │   ├── research.py       # Note, Wikilink
│   │   ├── notification.py
│   │   ├── portfolio.py
│   │   ├── session.py        # Session tokens
│   │   ├── llm_usage.py      # LLM cost tracking
│   │   └── automation.py
│   ├── services/             # Business logic layer
│   │   ├── audit.py          # Audit log creation
│   │   ├── embeddings.py     # OpenAI embeddings + pgvector
│   │   ├── forecasting.py    # ML budget forecasting (scikit-learn)
│   │   ├── market.py         # Market data API (Alpha Vantage)
│   │   ├── notifications.py  # Email/SMS delivery
│   │   ├── portfolio.py      # Asset tracking
│   │   ├── research.py       # Research plans, synthesis
│   │   ├── scheduling.py     # NL date parsing, conflict detection
│   │   ├── sessions.py       # JWT token management
│   │   ├── sms.py            # Twilio signature validation, command parsing
│   │   └── voice.py          # Whisper, TTS, intent parsing
│   ├── workers/              # Celery background tasks
│   │   ├── app.py            # Celery app config
│   │   └── tasks.py          # Scheduled tasks (recurring, refresh, backups)
│   ├── cli/                  # Click CLI commands
│   │   └── main.py           # All CLI commands
│   ├── utils/                # Utilities
│   │   ├── categorizer.py    # ML transaction categorization
│   │   ├── credibility.py    # Source credibility scoring
│   │   ├── dependencies.py   # Task dependency graph
│   │   ├── metrics.py        # Prometheus metrics
│   │   ├── ocr.py            # Tesseract receipt OCR
│   │   ├── ratelimit.py      # Rate limiting
│   │   ├── recurrence.py     # RRULE task recurrence
│   │   ├── resilience.py     # Circuit breakers
│   │   ├── security.py       # Password hashing, MFA
│   │   ├── storage.py        # MinIO file storage
│   │   ├── vendors.py        # Vendor normalization (fuzzy matching)
│   │   ├── versioning.py     # Git-backed note versioning
│   │   ├── wikilinks.py      # [[WikiLink]] parsing
│   │   └── arxiv_api.py      # arXiv search
│   ├── config.py             # Settings (Pydantic BaseSettings)
│   └── database.py           # SQLAlchemy async engine
├── web/                      # Next.js frontend
│   ├── src/
│   │   ├── app/              # App router pages
│   │   ├── components/       # React components (mobile-nav, etc.)
│   │   └── lib/              # API client, utilities
│   └── public/
│       └── manifest.json     # PWA manifest
├── tests/                    # Test suite (163 tests)
│   ├── conftest.py           # Pytest fixtures
│   ├── test_tasks.py
│   ├── test_finance.py
│   ├── test_forecasting.py
│   ├── test_categorizer_accuracy.py
│   ├── test_vendor_normalization.py
│   ├── test_research.py
│   ├── test_versioning.py
│   ├── test_synthesis.py
│   ├── test_voice.py
│   ├── test_sms.py
│   ├── test_scheduling.py
│   └── ...
├── alembic/                  # Database migrations
│   └── versions/             # 8+ migration files
├── scripts/                  # Operational scripts
│   ├── backup.sh             # Automated backups
│   └── restore.sh
├── config/                   # Systemd service templates
│   ├── nexus-api.service
│   ├── nexus-worker.service
│   └── nexus-beat.service
├── docker-compose.yml        # Infrastructure stack
├── pyproject.toml            # Python dependencies
├── .env.example              # Environment template
├── README.md                 # This file
├── SPECIFICATION.md          # Technical architecture
├── ROADMAP.md                # 20-week development plan (100% complete)
├── CHANGELOG.md              # Release history
├── CONTRIBUTING.md           # Contributor guide
└── LICENSE                   # MIT License
```

---

## ⚙️ Configuration

Copy `.env.example` to `.env` and configure:

### Required

```bash
# Database
DATABASE_URL=postgresql+asyncpg://nexus:password@localhost:5432/nexus_db

# Redis
REDIS_URL=redis://localhost:6379/0

# Security
NEXUS_SECRET_KEY=<generate with: openssl rand -hex 32>
NEXUS_ENCRYPTION_KEY=<generate with: openssl rand -hex 32>

# Environment
NEXUS_ENV=development  # or production
```

### Optional (Feature-Specific)

```bash
# OpenAI (required for voice, embeddings, LLM features)
OPENAI_API_KEY=sk-...

# Twilio (required for SMS gateway)
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1...

# MinIO (S3-compatible storage)
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=nexus

# Market Data (optional for portfolio)
ALPHA_VANTAGE_API_KEY=...

# Email (optional for notifications)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASSWORD=...
```

---

## 🧪 Development

### Running Tests

```bash
# Full suite (163 tests)
pytest

# With coverage
pytest --cov=nexus --cov-report=html

# Specific file
pytest tests/test_scheduling.py -v

# Watch mode
pytest-watch
```

### Code Quality

```bash
# Type checking
mypy src/

# Linting
ruff check src/

# Formatting
black src/ tests/
```

### Database Migrations

```bash
# Create migration
alembic revision --autogenerate -m "Add vendor_aliases table"

# Apply
alembic upgrade head

# Rollback
alembic downgrade -1

# Check current
alembic current
```

### Local Development

```bash
# Terminal 1: API server with hot reload
uvicorn nexus.api.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Celery worker
celery -A nexus.workers.app worker --loglevel=info

# Terminal 3: Celery beat scheduler
celery -A nexus.workers.app beat --loglevel=info

# Terminal 4: Next.js dev server (optional)
cd web && npm run dev

# Terminal 5: Run tests on file change
pytest-watch
```

---

## 🔒 Security

| Feature | Implementation |
|---------|----------------|
| **Authentication** | JWT access (15min) + refresh tokens (7d) |
| **MFA** | TOTP (30s window), encrypted secrets, backup codes |
| **Encryption** | AES-256 for sensitive fields (notes, MFA, SMS phone) |
| **Password Hashing** | bcrypt with salt |
| **Rate Limiting** | Per-user, per-endpoint (10 req/h for SMS) |
| **Audit Logging** | All mutations logged with IP, user-agent, timestamp |
| **Session Management** | Token invalidation, auto-refresh Celery task |
| **Circuit Breakers** | External service resilience (OpenAI, Twilio, OCR) |
| **CORS** | Configurable origins in production |

**Best Practices:**

1. Rotate `NEXUS_SECRET_KEY` and `NEXUS_ENCRYPTION_KEY` quarterly
2. Enable MFA for all users
3. Review audit logs weekly (`nexus audit logs`)
4. Use HTTPS in production (configure reverse proxy)
5. Backup database daily (see `scripts/backup.sh`)

See [SECURITY.md](SECURITY.md) for vulnerability disclosure.

---

## 📊 Monitoring & Operations

### Prometheus Metrics

Available at `GET /metrics`:

- `http_requests_total` — Request count by method/endpoint/status
- `http_request_duration_seconds` — Latency histogram
- `llm_usage_tokens_total` — Token usage by provider/model
- `llm_usage_cost_total` — Cumulative cost

### Health Check

```bash
curl http://localhost:8000/health
# {"status": "healthy", "env": "development"}
```

### Backup & Restore

```bash
# Backup (PostgreSQL + MinIO)
./scripts/backup.sh

# Restore
./scripts/restore.sh /path/to/backup.tar.gz
```

### Systemd Deployment

```bash
# Install service files
sudo cp config/*.service /etc/systemd/system/
sudo systemctl daemon-reload

# Start services
sudo systemctl enable nexus-api nexus-worker nexus-beat
sudo systemctl start nexus-api nexus-worker nexus-beat

# Check status
sudo systemctl status nexus-api
```

---

## 📖 Documentation

| Document | Description |
|----------|-------------|
| [SPECIFICATION.md](SPECIFICATION.md) | Complete technical architecture (140 pages) |
| [ROADMAP.md](ROADMAP.md) | 20-week development plan (100% complete) |
| [CHANGELOG.md](CHANGELOG.md) | Release history and migration notes |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Contributor guidelines |
| [GETTING_STARTED.md](GETTING_STARTED.md) | 30-minute tutorial |
| [docs/OPERATIONS.md](docs/OPERATIONS.md) | Production deployment guide |
| [docs/FAQ.md](docs/FAQ.md) | 40+ common questions |
| [SECURITY.md](SECURITY.md) | Security policy and best practices |

---

## 🤝 Contributing

Nexus is a personal project, but contributions are welcome!

**How to Contribute:**

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Write tests for new functionality
4. Ensure all tests pass (`pytest`)
5. Run code quality checks (`black src/ && mypy src/ && ruff check src/`)
6. Commit with conventional commits (`feat:`, `fix:`, `docs:`, etc.)
7. Push and open a Pull Request

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

---

## 🗺️ Roadmap Status

| Phase | Weeks | Status | Key Deliverables |
|-------|-------|--------|------------------|
| **Phase 1** | 1-4 | ✅ 100% | Infrastructure, Task Management, Smart Scheduling |
| **Phase 2** | 5-8 | ✅ 100% | Financial Intelligence, OCR, ML, Forecasting |
| **Phase 3** | 9-12 | ✅ 100% | Security, MFA, Monitoring, Backups |
| **Phase 4** | 13-16 | ✅ 100% | Research, Semantic Search, Git Versioning, Synthesis |
| **Phase 5** | 17-20 | ✅ 100% | Voice I/O, SMS Gateway, Mobile PWA |
| **Total** | 20 | ✅ 100% | **Full-featured Personal AI System** |

See [ROADMAP.md](ROADMAP.md) for task-level breakdown.

---

## 📊 Project Metrics

| Metric | Value |
|--------|-------|
| **Tests** | 163 passing |
| **Coverage** | 61% (3,282 statements) |
| **Lines of Code** | ~8,500 (src/) |
| **API Endpoints** | 40+ |
| **CLI Commands** | 30+ |
| **Database Tables** | 12 |
| **Celery Tasks** | 6 (recurring, refresh, backups) |
| **Dependencies** | 35 (production), 12 (dev) |

---

## 📞 Support

For questions, bug reports, or feature requests:

- 📖 **[Getting Started Guide](GETTING_STARTED.md)** — 30-minute tutorial
- 🔍 **[FAQ](docs/FAQ.md)** — 40+ common questions answered
- 💬 **[GitHub Discussions](https://github.com/calvin/nexus/discussions)** — General questions
- 🐛 **[Bug Reports](.github/ISSUE_TEMPLATE/bug_report.md)** — Use the bug template
- ✨ **[Feature Requests](.github/ISSUE_TEMPLATE/feature_request.md)** — Use the feature template
- 📧 **Private Contact** — calvinbrady8@gmail.com

> **Note:** This is a personal project maintained during free time. Response times may vary, but all issues and PRs are reviewed.

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

**Built with ❤️ for personal productivity, privacy, and autonomy.**

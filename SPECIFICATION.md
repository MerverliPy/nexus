# Nexus Personal AI System - Technical Specification

**Version:** 1.0.0  
**Last Updated:** 2026-07-09  
**Status:** Pre-Development

---

## Executive Summary

**Nexus** is a self-hosted, privacy-first personal AI system designed to augment human intelligence across three core domains: everyday task management, financial intelligence, and research workflows. Unlike fragmented SaaS solutions that require juggling multiple apps, Nexus provides a unified data model and cross-domain reasoning capabilities.

**Core Value Proposition:**
- **Unified Intelligence**: Research findings inform investment decisions; financial constraints shape project timelines
- **Privacy-First**: Self-hosted on user infrastructure, no third-party data sharing
- **Learning System**: Improves accuracy through supervised learning from user corrections
- **Proactive Assistance**: Monitors, alerts, and suggests actions without prompting

**Target User:** Technical power user comfortable with CLI, values privacy, wants production-grade reliability for 24/7 personal automation.

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     INTERACTION LAYER                        │
├───────────┬───────────┬──────────┬──────────┬──────────────┤
│    CLI    │    Web    │   SMS    │  Email   │    Voice     │
│ (Primary) │ Dashboard │ Gateway  │  Bridge  │  Interface   │
└─────┬─────┴─────┬─────┴────┬─────┴────┬─────┴──────┬───────┘
      │           │          │          │            │
      └───────────┴──────────┴──────────┴────────────┘
                           │
                    ┌──────▼──────┐
                    │  FastAPI    │
                    │  Backend    │
                    │  (async)    │
                    └──────┬──────┘
                           │
      ┌────────────────────┼────────────────────┐
      │                    │                    │
┌─────▼─────┐      ┌──────▼──────┐     ┌──────▼──────┐
│  Auth &   │      │   Business  │     │  Background │
│  Security │      │    Logic    │     │   Workers   │
│  (MFA)    │      │   Routers   │     │  (Celery)   │
└─────┬─────┘      └──────┬──────┘     └──────┬──────┘
      │                    │                    │
      └────────────────────┼────────────────────┘
                           │
      ┌────────────────────┼────────────────────┐
      │                    │                    │
┌─────▼─────┐      ┌──────▼──────┐     ┌──────▼──────┐
│PostgreSQL │      │    Redis    │     │   MinIO     │
│ +pgvector │      │   (cache,   │     │  (S3-API)   │
│           │      │    queue)   │     │  Documents  │
└───────────┘      └─────────────┘     └─────────────┘
                           │
                    ┌──────▼──────┐
                    │  External   │
                    │  Services   │
                    ├─────────────┤
                    │ • LLM APIs  │
                    │ • Bank APIs │
                    │ • Market    │
                    │ • Email     │
                    └─────────────┘
```

### Technology Stack

#### Backend
- **Framework:** FastAPI 0.110+ (async-native Python web framework)
- **Task Queue:** Celery 5.3+ with Redis broker
- **ORM:** SQLAlchemy 2.0+ with async support
- **Migrations:** Alembic 1.13+
- **Validation:** Pydantic 2.0+ (native FastAPI integration)
- **Authentication:** python-jose (JWT), passlib (password hashing), pyotp (TOTP/MFA)
- **API Client Libraries:** httpx (async HTTP), tenacity (retry logic), circuitbreaker

#### Data Layer
- **Primary Database:** PostgreSQL 16+ with pgvector 0.6+
- **Cache/Queue:** Redis 7.2+ with AOF persistence enabled
- **Object Storage:** MinIO (S3-compatible) for documents, receipts, attachments
- **Vector Embeddings:** OpenAI text-embedding-3-small or local (all-MiniLM-L6-v2)

#### Frontend
- **Web Framework:** Next.js 14+ (App Router)
- **UI Components:** shadcn/ui (Radix UI + Tailwind)
- **Charts:** Recharts 2.10+
- **Forms:** React Hook Form + Zod validation
- **State Management:** Zustand (lightweight, no boilerplate)
- **Real-time:** Socket.IO client for live updates

#### CLI
- **Framework:** Click 8.1+ (command groups, auto-completion)
- **UI:** Rich 13+ (tables, progress bars, syntax highlighting)
- **Configuration:** TOML-based config in `~/.nexus/config.toml`

#### ML/AI
- **OCR:** PyTesseract + LayoutLM/Donut for receipts
- **Categorization:** scikit-learn (LogisticRegression, incremental learning)
- **NLP:** spaCy for intent parsing
- **LLM Integration:** LiteLLM (unified API for OpenAI, Anthropic, etc.)

#### Infrastructure
- **Reverse Proxy:** Caddy 2.7+ (automatic HTTPS)
- **Monitoring:** Grafana 10+ + Prometheus 2.48+
- **Process Manager:** systemd (WSL2 native support)
- **Logging:** structlog (structured JSON logs)
- **Alerting:** Telegram Bot API (system health notifications)

---

## Data Architecture

### Entity Relationship Diagram

```
┌─────────────┐       ┌──────────────┐       ┌─────────────┐
│    User     │───────│  AuthToken   │       │  AuditLog   │
│             │       │  (MFA/JWT)   │       │             │
├─────────────┤       └──────────────┘       ├─────────────┤
│ id (PK)     │                              │ id (PK)     │
│ email       │                              │ user_id (FK)│
│ password_   │                              │ action      │
│   hash      │                              │ timestamp   │
│ totp_secret │                              │ ip_address  │
│ created_at  │                              │ details     │
└──────┬──────┘                              └─────────────┘
       │
       ├──────────────────────┬──────────────────────┬─────────────────┐
       │                      │                      │                 │
┌──────▼──────┐        ┌──────▼──────┐       ┌──────▼──────┐   ┌─────▼─────┐
│   Task      │        │Transaction  │       │    Note     │   │ Automation│
├─────────────┤        ├─────────────┤       ├─────────────┤   ├───────────┤
│ id (PK)     │        │ id (PK)     │       │ id (PK)     │   │ id (PK)   │
│ user_id(FK) │        │ user_id(FK) │       │ user_id(FK) │   │ user_id   │
│ title       │        │ amount      │       │ title       │   │ name      │
│ description │        │ vendor      │       │ content     │   │ schedule  │
│ status      │        │ category    │       │ tags[]      │   │ enabled   │
│ due_date    │        │ date        │       │ embedding   │   │ last_run  │
│ recurrence  │        │ account_id  │       │ project_id  │   │ config    │
└─────────────┘        │ receipt_url │       └──────┬──────┘   └───────────┘
                       │ is_verified │              │
                       └──────┬──────┘              │
                              │                     │
                       ┌──────▼──────┐       ┌──────▼──────┐
                       │  Account    │       │ NoteLink    │
                       ├─────────────┤       ├─────────────┤
                       │ id (PK)     │       │ from_note   │
                       │ user_id(FK) │       │ to_note     │
                       │ name        │       │ created_at  │
                       │ type        │       └─────────────┘
                       │ institution │
                       │ balance     │
                       │ encrypted_  │
                       │   token     │
                       └─────────────┘
```

### Database Schema

#### Core Tables

**users**
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    totp_secret VARCHAR(32),  -- Encrypted, NULL if MFA not enabled
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);
```

**tasks**
```sql
CREATE TABLE tasks (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    status VARCHAR(20) DEFAULT 'pending',  -- pending, in_progress, completed, cancelled
    priority INTEGER DEFAULT 0,
    due_date TIMESTAMP,
    recurrence_rule VARCHAR(100),  -- RRULE format (RFC 5545)
    context JSONB,  -- Flexible metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_tasks_user_status ON tasks(user_id, status);
CREATE INDEX idx_tasks_due_date ON tasks(due_date) WHERE status != 'completed';
```

**transactions**
```sql
CREATE TABLE transactions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    account_id INTEGER REFERENCES accounts(id) ON DELETE SET NULL,
    amount DECIMAL(12, 2) NOT NULL,
    vendor VARCHAR(255),
    category VARCHAR(100),
    description TEXT,
    transaction_date DATE NOT NULL,
    is_verified BOOLEAN DEFAULT FALSE,
    receipt_url VARCHAR(500),
    metadata JSONB,  -- OCR output, original bank description, etc.
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_transactions_user_date ON transactions(user_id, transaction_date DESC);
CREATE INDEX idx_transactions_category ON transactions(user_id, category);
CREATE INDEX idx_transactions_vendor ON transactions(vendor);
```

**accounts**
```sql
CREATE TABLE accounts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    account_type VARCHAR(50) NOT NULL,  -- checking, savings, credit_card, investment
    institution VARCHAR(255),
    balance DECIMAL(12, 2) DEFAULT 0,
    encrypted_credentials TEXT,  -- AES-256 encrypted Plaid token or credentials
    last_synced_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_accounts_user_type ON accounts(user_id, account_type);
```

**notes**
```sql
CREATE TABLE notes (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    project_id INTEGER REFERENCES research_projects(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    tags TEXT[],
    embedding vector(1536),  -- pgvector, dimension matches embedding model
    source_url TEXT,
    source_type VARCHAR(50),  -- web, paper, book, conversation
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_notes_user ON notes(user_id);
CREATE INDEX idx_notes_project ON notes(project_id);
CREATE INDEX idx_notes_tags ON notes USING GIN(tags);
CREATE INDEX idx_notes_embedding ON notes USING ivfflat(embedding vector_cosine_ops) WITH (lists = 100);
```

**note_links**
```sql
CREATE TABLE note_links (
    id SERIAL PRIMARY KEY,
    from_note_id INTEGER REFERENCES notes(id) ON DELETE CASCADE,
    to_note_id INTEGER REFERENCES notes(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(from_note_id, to_note_id)
);

CREATE INDEX idx_note_links_from ON note_links(from_note_id);
CREATE INDEX idx_note_links_to ON note_links(to_note_id);
```

**automations**
```sql
CREATE TABLE automations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    automation_type VARCHAR(50) NOT NULL,  -- cron, file_watch, email_rule, webhook
    schedule VARCHAR(100),  -- For cron: '0 9 * * 1', 'every 30m'
    trigger_config JSONB,  -- File patterns, email filters, webhook URLs
    action_config JSONB,  -- What to execute
    is_enabled BOOLEAN DEFAULT TRUE,
    last_run_at TIMESTAMP,
    last_status VARCHAR(20),  -- success, failure, pending
    run_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_automations_user_enabled ON automations(user_id, is_enabled);
CREATE INDEX idx_automations_schedule ON automations(schedule) WHERE is_enabled = TRUE;
```

**audit_logs**
```sql
CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,  -- 'login', 'transaction_create', 'automation_run', etc.
    resource_type VARCHAR(50),
    resource_id INTEGER,
    ip_address INET,
    user_agent TEXT,
    details JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_user_action ON audit_logs(user_id, action, created_at DESC);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at DESC);
```

---

## Security Architecture

### Authentication & Authorization

**Multi-Factor Authentication (MFA)**
- TOTP-based (Time-based One-Time Password) using pyotp
- QR code generation for enrollment via qrcode library
- 6-digit codes with 30-second window
- Backup codes stored encrypted (10 single-use codes)

**Session Management**
- JWT tokens with 1-hour expiration
- Refresh tokens with 7-day expiration (stored in Redis, revocable)
- Device fingerprinting (user agent + IP hashing)
- Concurrent session limit: 3 devices

**Password Policy**
- Minimum 12 characters
- Argon2id hashing (passlib default)
- Salted, slow hashing (prevents rainbow table attacks)
- Password breach check via haveibeenpwned API (k-anonymity)

### Data Protection

**Encryption at Rest**
- Database-level: PostgreSQL transparent data encryption (TDE) or LUKS volume
- Field-level: SQLAlchemy-utils EncryptedType for sensitive fields
  - Account credentials (Plaid tokens)
  - TOTP secrets
  - Backup codes
- Encryption key: Stored in environment variable (not in repo), rotated quarterly

**Encryption in Transit**
- TLS 1.3 for all HTTP traffic (Caddy auto-HTTPS)
- Certificate: Let's Encrypt with auto-renewal
- HSTS enabled (Strict-Transport-Security header)

**Sensitive Data Handling**
- PII redaction before LLM API calls (regex + NER-based detection)
- Local LLM fallback for financial queries (Ollama + Mistral 7B)
- No financial data in logs (structlog processor filters amounts, account numbers)

### API Security

**Rate Limiting**
- Per-user: 100 requests/minute (normal), 10 requests/minute (auth endpoints)
- Per-IP: 1000 requests/hour (prevents brute force)
- Implementation: Redis-backed sliding window (fastapi-limiter)

**Circuit Breakers**
- External APIs (LLM, bank, market data): 5 failures → 10-minute cooldown
- Implementation: circuitbreaker library

**Input Validation**
- Pydantic models for all API inputs (automatic validation)
- SQL injection prevention: SQLAlchemy parameterized queries
- XSS prevention: FastAPI auto-escapes template output

### Audit Trail

**Immutable Logging**
- All sensitive actions logged to `audit_logs` table
- Append-only (no UPDATE or DELETE on audit_logs)
- Logged actions:
  - Authentication (login, logout, MFA enrollment)
  - Financial (transaction create/edit, automation run)
  - Configuration (automation enable/disable, account link)
  - Data export (note export, transaction CSV download)

---

## API Design

### RESTful Endpoints

**Base URL:** `http://localhost:8000/api/v1`

#### Authentication
```
POST   /auth/register         Register new user
POST   /auth/login            Login (returns JWT + refresh token)
POST   /auth/refresh          Refresh access token
POST   /auth/logout           Logout (revoke refresh token)
POST   /auth/mfa/enroll       Generate TOTP secret + QR code
POST   /auth/mfa/verify       Verify TOTP code to enable MFA
POST   /auth/mfa/disable      Disable MFA (requires password + TOTP)
```

#### Tasks
```
GET    /tasks                 List tasks (filter: status, due_date)
POST   /tasks                 Create task
GET    /tasks/{id}            Get task details
PATCH  /tasks/{id}            Update task
DELETE /tasks/{id}            Delete task
POST   /tasks/{id}/complete   Mark complete
POST   /tasks/batch           Bulk create/update tasks
```

#### Transactions
```
GET    /transactions          List transactions (filter: date_range, category, account)
POST   /transactions          Create transaction
GET    /transactions/{id}     Get transaction details
PATCH  /transactions/{id}     Update transaction (triggers retraining)
DELETE /transactions/{id}     Delete transaction
POST   /transactions/upload   Upload receipt photo → OCR → transaction
POST   /transactions/import   Import CSV (bank statement)
GET    /transactions/categories   Get category suggestions for vendor
POST   /transactions/{id}/verify  Mark transaction as verified
```

#### Accounts
```
GET    /accounts              List accounts
POST   /accounts              Create account
GET    /accounts/{id}         Get account details
PATCH  /accounts/{id}         Update account
DELETE /accounts/{id}         Delete account (soft delete)
POST   /accounts/{id}/sync    Trigger Plaid sync
GET    /accounts/summary      Aggregate balances, net worth
```

#### Research / Notes
```
GET    /notes                 List notes (filter: tags, project)
POST   /notes                 Create note
GET    /notes/{id}            Get note details
PATCH  /notes/{id}            Update note (regenerates embedding)
DELETE /notes/{id}            Delete note
POST   /notes/search          Semantic search (query → vector similarity)
GET    /notes/{id}/links      Get linked notes (graph)
POST   /notes/{id}/links      Create note link
GET    /projects              List research projects
POST   /projects              Create research project
POST   /research/deep-dive    Trigger automated research workflow
```

#### Automations
```
GET    /automations           List automations
POST   /automations           Create automation
GET    /automations/{id}      Get automation details
PATCH  /automations/{id}      Update automation
DELETE /automations/{id}      Delete automation
POST   /automations/{id}/enable   Enable automation
POST   /automations/{id}/disable  Disable automation
POST   /automations/{id}/run      Manually trigger automation
GET    /automations/{id}/logs     Get execution history
```

#### Analytics
```
GET    /analytics/spending    Spending breakdown (by category, time period)
GET    /analytics/trends      Cash flow forecast, spending trends
GET    /analytics/net-worth   Net worth over time
GET    /analytics/budget      Budget vs actual, alerts
```

### WebSocket Endpoints

**Real-time Updates:** `ws://localhost:8000/ws`

Events pushed to connected clients:
- `transaction.created` → Update dashboard totals
- `automation.completed` → Show notification
- `research.progress` → Update progress bar
- `system.alert` → Critical system notifications

---

## Machine Learning Pipeline

### Transaction Categorization

**Training Data:**
- Initial: 100+ hand-labeled examples per category (bootstrapped)
- Ongoing: Incremental learning from user corrections

**Feature Engineering:**
```python
features = [
    'vendor_name_clean',      # Normalized vendor string
    'amount',                 # Transaction amount
    'day_of_week',            # Monday=0, Sunday=6
    'hour_of_day',            # If timestamp available
    'is_recurring',           # Binary: detected 3+ identical
    'vendor_category_prior',  # Historical category for vendor
]
```

**Model:**
- Algorithm: Logistic Regression (scikit-learn)
- Updates: Incremental learning via `partial_fit()` every 10 corrections
- Metrics: Accuracy, precision, recall per category (logged to PostgreSQL)
- Threshold: Prediction confidence < 70% → prompt user for manual categorization

**Vendor Normalization:**
- Alias table: `vendor_aliases` (user-corrected mappings)
- Example: "SQ *COFFEE SHOP", "COFFEE SHOP #123" → "Coffee Shop"
- Fuzzy matching: RapidFuzz with 85% threshold for new vendors

### Receipt OCR Pipeline

**Preprocessing:**
1. Image upload → MinIO storage
2. Orientation correction (PIL + pytesseract OSD)
3. Contrast enhancement (OpenCV adaptive threshold)

**Extraction:**
- **Method 1 (Fast):** PyTesseract + regex patterns for vendor, amount, date
- **Method 2 (Accurate):** LayoutLM inference for structured extraction
- Fallback: If Method 1 confidence < 60%, use Method 2

**Post-processing:**
- Date normalization (dateutil.parser)
- Amount validation (regex: `\$?\d+\.\d{2}`)
- Vendor lookup in existing transactions (fuzzy match)

**User Confirmation:**
- Extracted data shown in CLI/web UI for verification
- User edits → feedback loop for OCR model tuning

---

## Deployment Architecture (WSL2)

### Directory Structure
```
/home/user/nexus/
├── venv/                    # Python virtual environment
├── src/
│   ├── nexus/
│   │   ├── api/             # FastAPI routers
│   │   ├── models/          # SQLAlchemy models
│   │   ├── services/        # Business logic
│   │   ├── workers/         # Celery tasks
│   │   ├── cli/             # Click commands
│   │   └── utils/           # Helpers
│   └── migrations/          # Alembic migrations
├── config/
│   ├── config.prod.toml     # Production config
│   └── config.dev.toml      # Development config
├── scripts/
│   ├── setup.sh             # One-time setup
│   ├── backup.sh            # Daily backup script
│   └── health-check.sh      # Uptime monitoring
├── logs/                    # Application logs
├── backups/                 # Database backups
└── docker-compose.yml       # For PostgreSQL, Redis, MinIO
```

### systemd Services

**nexus-backend.service**
```ini
[Unit]
Description=Nexus FastAPI Backend
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=calvin
WorkingDirectory=/home/calvin/nexus
Environment="PATH=/home/calvin/nexus/venv/bin"
ExecStart=/home/calvin/nexus/venv/bin/uvicorn nexus.api.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**nexus-worker.service**
```ini
[Unit]
Description=Nexus Celery Worker
After=network.target redis.service

[Service]
Type=simple
User=calvin
WorkingDirectory=/home/calvin/nexus
Environment="PATH=/home/calvin/nexus/venv/bin"
ExecStart=/home/calvin/nexus/venv/bin/celery -A nexus.workers.app worker --loglevel=info
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Backup Strategy

**Daily Automated Backups:**
```bash
#!/bin/bash
# scripts/backup.sh
BACKUP_DIR=/home/calvin/nexus/backups
DATE=$(date +%Y%m%d_%H%M%S)

# PostgreSQL backup
pg_dump nexus_db -U nexus_user | gzip > "$BACKUP_DIR/db_$DATE.sql.gz"

# MinIO backup (using mc client)
mc mirror local/nexus-receipts s3/nexus-backup/receipts/

# Encrypt backup
gpg --encrypt --recipient backup@nexus.local "$BACKUP_DIR/db_$DATE.sql.gz"

# Upload to cloud (Backblaze B2)
b2 upload-file nexus-backup "$BACKUP_DIR/db_$DATE.sql.gz.gpg" "backups/db_$DATE.sql.gz.gpg"

# Retain: 7 daily, 4 weekly, 12 monthly
# Delete backups older than 90 days
find "$BACKUP_DIR" -name "db_*.sql.gz*" -mtime +90 -delete
```

**Backup Restoration Testing:**
- Weekly automated test: Restore last backup to staging DB → run health check
- Alert on failure via Telegram

---

## Monitoring & Observability

### Metrics (Prometheus)

**Application Metrics:**
- HTTP request rate, latency, error rate (per endpoint)
- Celery task queue depth, task duration, failure rate
- Database connection pool usage
- LLM API: requests/min, tokens used, cost estimate
- OCR pipeline: receipts processed, success rate

**System Metrics:**
- CPU, memory, disk usage
- PostgreSQL: query duration, cache hit rate, active connections
- Redis: memory usage, eviction rate
- MinIO: storage used, request rate

**Business Metrics:**
- Transactions logged per day
- Categorization accuracy (daily average)
- Active automations count
- Research queries executed per week

### Dashboards (Grafana)

**System Health Dashboard:**
- Service uptime (nexus-backend, nexus-worker, PostgreSQL, Redis)
- Error rate (4xx, 5xx responses)
- Request latency (p50, p95, p99)
- Celery queue depth over time

**Financial Intelligence Dashboard:**
- Transactions per day (bar chart)
- Categorization accuracy trend (line chart)
- Top spending categories (pie chart)
- Budget vs actual (gauge)

**Cost Monitoring Dashboard:**
- LLM API tokens used per day
- Estimated monthly cost (projection)
- Cost per domain (tasks, finance, research)
- Alert threshold: $50/month

### Alerting Rules

**Critical Alerts (Telegram):**
- Any service down for >2 minutes
- Disk usage >90%
- Database backup failed
- LLM API cost >$5/day
- Authentication failures >10/hour (potential attack)

**Warning Alerts (Email):**
- Celery queue depth >100 for >10 minutes
- Categorization accuracy <80% for 3 consecutive days
- Automation failure rate >10% for any automation

---

## Testing Strategy

### Test Pyramid

**Unit Tests (70%):**
- Models: ORM operations, validation
- Services: Business logic (mocked dependencies)
- Utils: Helper functions, data transformations
- Target: 80% code coverage

**Integration Tests (20%):**
- API endpoints: Request → DB → Response
- Celery tasks: Task execution with real Redis
- Database: Migrations, queries, indexes
- External APIs: Mocked with pytest-httpx

**End-to-End Tests (10%):**
- User workflows: Register → Create task → Complete
- Financial flows: Upload receipt → OCR → Categorized transaction
- Research flows: Deep dive → Generate notes → Semantic search

### CI/CD Pipeline (GitHub Actions)

```yaml
name: CI
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_PASSWORD: test
      redis:
        image: redis:7.2
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -e ".[dev]"
      - run: pytest --cov=nexus --cov-report=xml
      - run: mypy src/
      - run: ruff check src/

  deploy:
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to WSL2
        run: |
          ssh wsl2-host "cd /home/calvin/nexus && git pull && systemctl --user restart nexus-backend nexus-worker"
```

---

## Performance Targets

### Response Time SLAs

| Endpoint | Target (p95) | Max Acceptable |
|----------|--------------|----------------|
| GET /tasks | 50ms | 200ms |
| POST /transactions | 100ms | 500ms |
| POST /transactions/upload (OCR) | 3s | 10s |
| POST /notes/search (semantic) | 200ms | 1s |
| POST /research/deep-dive | 30s | 2min |

### Scalability Targets

- **Transactions:** Handle 10,000 transactions/month without performance degradation
- **Notes:** 50,000 notes with sub-second semantic search
- **Concurrent Users:** 1 (single-user system, but multi-device)
- **Automation Jobs:** 50 scheduled tasks running concurrently

### Resource Budget

- **Disk:** <10 GB for 1 year of data (excluding receipt images)
- **Memory:** <2 GB backend + 1 GB worker + 2 GB databases = 5 GB total
- **CPU:** <20% average utilization on 4-core system
- **LLM API Cost:** <$50/month (target: $30/month)

---

## Risk Register

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| WSL2 Windows update restarts system | High | High | systemd auto-restart + uptime monitoring + Telegram alert |
| LLM API outage | Medium | Medium | Local LLM fallback (Ollama), job queue for retry |
| PostgreSQL corruption | Low | High | Daily backups + weekly restoration tests |
| Runaway automation costs | Medium | High | Per-automation rate limits + cost budget alerts |
| Receipt OCR accuracy <70% | Medium | Medium | LayoutLM fallback + user confirmation workflow |
| Plaid API token expiration | High | Medium | 30-day token refresh + user notification before expiry |
| Security breach (credential theft) | Low | High | MFA mandatory, encrypted fields, audit trail |
| Scope creep (feature bloat) | High | Medium | Strict Phase-based roadmap, feature freeze periods |

---

## Dependencies & Licenses

### Python Dependencies (requirements.txt)
```
# Web framework
fastapi==0.110.0
uvicorn[standard]==0.27.0
pydantic==2.6.0
pydantic-settings==2.1.0

# Database
sqlalchemy==2.0.25
alembic==1.13.1
asyncpg==0.29.0
pgvector==0.2.4
psycopg2-binary==2.9.9

# Cache & Queue
redis==5.0.1
celery==5.3.6

# Auth & Security
python-jose[cryptography]==3.3.0
passlib[argon2]==1.7.4
python-multipart==0.0.9
pyotp==2.9.0
qrcode==7.4.2
cryptography==42.0.2
sqlalchemy-utils==0.41.1

# HTTP & APIs
httpx==0.26.0
tenacity==8.2.3
circuitbreaker==1.4.0
litellm==1.23.0

# ML & NLP
scikit-learn==1.4.0
spacy==3.7.2
sentence-transformers==2.3.1

# OCR
pytesseract==0.3.10
Pillow==10.2.0
opencv-python==4.9.0.80

# CLI
click==8.1.7
rich==13.7.0

# Logging & Monitoring
structlog==24.1.0
prometheus-client==0.19.0

# Testing
pytest==8.0.0
pytest-asyncio==0.23.4
pytest-cov==4.1.0
pytest-httpx==0.28.0
```

### License
- **Nexus Core:** MIT License (permissive, allows commercial use)
- **Dependencies:** Primarily MIT/Apache 2.0 (verify pgvector GPL compatibility)

---

## Glossary

- **Automation:** Scheduled or event-driven task executed by the system without user intervention
- **Deep Dive:** Automated research workflow that generates research plan → executes searches → synthesizes findings
- **Embedding:** Vector representation of text (note content) used for semantic search
- **OCR:** Optical Character Recognition - extracting text from images
- **Semantic Search:** Finding notes by meaning rather than keyword matching (uses vector similarity)
- **TOTP:** Time-based One-Time Password - 6-digit code that changes every 30 seconds (MFA)
- **Vendor Normalization:** Mapping various bank transaction descriptions to canonical vendor names

---

## Appendices

### A. CLI Command Reference (Preview)

```bash
# Tasks
nexus task add "Review insurance policy" --due "next week"
nexus task list --status pending
nexus task complete <id>

# Finance
nexus finance log 50 "Coffee" --category "Dining"
nexus finance upload ~/receipt.jpg
nexus finance report --month "2026-07"

# Research
nexus research "Compare investment portfolios: S&P 500 vs All Weather"
nexus note create "Investment Strategy 2026" --project investing
nexus note search "portfolio rebalancing"

# Automation
nexus auto create "Weekly Spending Summary" --schedule "every monday 9am" --action "nexus finance report --last-week | nexus email send"
nexus auto list
nexus auto disable <id>

# System
nexus status
nexus logs --tail 50
nexus backup now
```

### B. Configuration File Schema

**~/.nexus/config.toml**
```toml
[database]
host = "localhost"
port = 5432
database = "nexus_db"
user = "nexus_user"
password = "${NEXUS_DB_PASSWORD}"  # Environment variable

[redis]
host = "localhost"
port = 6379
db = 0

[minio]
endpoint = "localhost:9000"
access_key = "${MINIO_ACCESS_KEY}"
secret_key = "${MINIO_SECRET_KEY}"
bucket = "nexus-data"

[llm]
provider = "openrouter"
model = "anthropic/claude-3-5-sonnet"
api_key = "${OPENROUTER_API_KEY}"
fallback_model = "ollama/mistral:7b-instruct"
max_monthly_cost = 50.0

[security]
secret_key = "${NEXUS_SECRET_KEY}"  # For JWT signing
mfa_issuer = "Nexus"
session_timeout_hours = 1
refresh_token_days = 7

[notifications]
telegram_bot_token = "${TELEGRAM_BOT_TOKEN}"
telegram_chat_id = "${TELEGRAM_CHAT_ID}"
email_smtp_host = "smtp.gmail.com"
email_smtp_port = 587
email_from = "${NEXUS_EMAIL}"

[features]
enable_plaid = false  # Bank integration
enable_voice = false  # Voice interface
enable_sms = true     # SMS gateway
```

---

**End of Specification**

*This document is a living specification and will be updated as the project evolves.*

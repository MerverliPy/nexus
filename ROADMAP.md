# Nexus Personal AI System - Implementation Roadmap

**Version:** 1.0.0  
**Timeline:** 20 weeks (5 months)  
**Last Updated:** 2026-07-11 (annotated with actual implementation state)

---

## Overview

This roadmap breaks the Nexus project into 5 concrete phases, each building on the previous one. Each phase delivers a working, testable increment of functionality.

**Key Principles:**
- ✅ **Vertical slices**: Each phase delivers end-to-end functionality (not "frontend done, backend next")
- ✅ **Security-first**: MFA and encryption come early, not as afterthoughts
- ✅ **Test-driven**: Tests written alongside code, 80% coverage minimum
- ✅ **Incremental learning**: Start simple, add complexity as understanding deepens

**Total Estimated Effort:** 480 hours (~24 hours/week for 20 weeks, or 12 hours/week for 40 weeks)

---

## 📊 Implementation Status (as of 2026-07-11)

> **Snapshot:** Phases 1–2 built end-to-end. Phase 3 security layer (MFA, sessions, audit, encryption) + production layer (metrics, backups, systemd, circuit breaker, LLM cost model) all wired & tested. **Celery worker app now implemented** — the cross-cutting async gate is closed. Current working line: **finishing Phase 3 → ready for Phase 4**.

**Legend:** `[x]` done · `[~]` partial / scaffolded · `[ ]` not started

| Phase | Status | Summary |
|-------|--------|---------|
| **1 — Foundation** | ✅ ~95% | Infra, JWT auth, tasks, Next.js web, WebSocket live. Celery worker now generates recurring task instances. |
| **2 — Finance** | ✅ 100% | CRUD, CSV import, analytics, OCR, ML categorization, accuracy tracking, vendor normalization — all done. |
| **3 — Security/Prod** | 🟡 ~45% | All W9-10 done. W11-12: Prometheus /metrics, backup+restore scripts, systemd templates, circuit breaker, LLM cost model all in place. |
| **4 — Research** | 🟡 ~85% | Notes, wiki-links, hybrid search, arXiv, credibility scoring, LLM plans, export, git versioning — all live & tested. |
| **5 — Advanced** | ✅ 100% | Portfolio + net-worth + notification bundling + ML forecasting + voice (STT+TTS) + SMS gateway + mobile PWA — all done. |

**Two systemic gaps cut across phases:**
1. ~~**No Celery workers**~~ ✅ **RESOLVED** — `src/nexus/workers/` now has `app.py` (Celery + beat schedule) and `tasks.py` (recurring-task generation, ML retraining, DB backup, session cleanup). Redis-brokered; tasks auto-discovered.
2. **Declared-but-unused dependencies** — mostly resolved: `pyotp`, `tenacity`, `circuitbreaker`, `prometheus-client`, `celery` are all now wired. `sentence-transformers` remains unused (Phase 4 semantic search).

---

## Phase 1: Foundation & Task Management (Weeks 1-4)

**Goal:** Build the core infrastructure and basic task management. By the end of Phase 1, you should have a working CLI and web dashboard for managing tasks.

### Week 1-2: Infrastructure Setup

#### Deliverables — ✅ DONE
- [x] PostgreSQL + Redis + MinIO Docker Compose setup *(+ Prometheus & Grafana already added)*
- [x] FastAPI project structure with SQLAlchemy models
- [x] Alembic migrations initialized *(1 migration: initial_schema)*
- [x] Basic auth (JWT, no MFA yet) *(register/login/refresh/me)*
- [x] CLI framework with Click *(auth/task/finance/note/status groups)*
- [x] pytest test suite skeleton *(⚠ only 5 tests total — far below the 80% coverage goal)*

#### Tasks
1. **Project scaffolding** (4h)
   ```bash
   uv venv venv
   source venv/bin/activate
   uv pip install fastapi sqlalchemy alembic asyncpg redis celery click rich pytest
   ```
   - Create `src/nexus/` package structure
   - Setup `pyproject.toml` with dependencies
   - Configure `alembic.ini` for migrations

2. **Database setup** (6h)
   - Write `docker-compose.yml` for PostgreSQL 16 + pgvector, Redis, MinIO
   - Create initial models: `User`, `Task`
   - First migration: `alembic revision --autogenerate -m "Initial schema"`
   - Connection pooling configuration (asyncpg)

3. **FastAPI backend basics** (8h)
   - `api/main.py`: App initialization, middleware (CORS, logging)
   - `api/auth.py`: JWT authentication (login, register)
   - `api/tasks.py`: CRUD endpoints for tasks
   - Pydantic schemas for request/response validation
   - Error handling (custom exception handlers)

4. **CLI basics** (6h)
   - `cli/main.py`: Click command groups
   - `nexus auth login` → store JWT in `~/.nexus/token`
   - `nexus task add "Title" --due "tomorrow"`
   - `nexus task list --status pending`
   - Rich output formatting (tables, colors)

5. **Testing infrastructure** (4h)
   - `conftest.py`: pytest fixtures (test DB, test client)
   - Test database factory with Docker (testcontainers-python)
   - Sample tests: `test_auth.py`, `test_tasks.py`
   - CI config: `.github/workflows/ci.yml` (pytest, mypy, ruff)

**Effort:** 28 hours  
**Success Criteria:**
- ✅ Can register user, login, create/list/complete tasks via CLI
- ✅ All tests pass (pytest)
- ✅ FastAPI docs accessible at `http://localhost:8000/docs`

---

### Week 3-4: Web Dashboard & Task Intelligence

#### Deliverables — 🟡 MOSTLY DONE
- [x] Next.js web dashboard (task list, create, complete)
- [x] Real-time updates via WebSocket *(ws.py + ws_manager.py)*
- [x] Recurring tasks (RRULE format) *(recurrence.py + Celery generate_recurring_tasks task, hourly beat schedule; tested)*
- [~] Task dependencies and smart scheduling *(dependencies.py util exists; smart scheduling not wired)*

#### Tasks
1. **Next.js setup** (6h)
   - `npx create-next-app@latest nexus-web --typescript --tailwind --app`
   - Install shadcn/ui components (button, card, table, form)
   - API client with `fetch` (reusable hooks: `useTasks()`)
   - Auth context (JWT storage in localStorage)

2. **Task dashboard UI** (8h)
   - Task list with filters (status, due date)
   - Create task form (React Hook Form + Zod)
   - Task detail view (edit, complete, delete)
   - Due date picker (react-day-picker)
   - Responsive layout (mobile-friendly)

3. **Real-time updates** (6h)
   - Backend: Socket.IO integration (`fastapi-socketio`)
   - Emit events on task create/update/complete
   - Frontend: Socket.IO client, auto-refresh task list
   - Connection status indicator

4. **Recurring tasks** (6h)
   - Parse RRULE strings (python-dateutil.rrule)
   - Celery beat scheduler for generating task instances
   - CLI: `nexus task add "Weekly review" --recur "FREQ=WEEKLY;BYDAY=MO"`
   - UI: Recurrence picker (daily/weekly/monthly presets)

5. **Smart scheduling** (6h)
   - Natural language date parsing ("next week", "tomorrow 3pm")
   - Context-aware defaults (learn user's preferred time)
   - Conflict detection (overlapping tasks)
   - Suggested times (free slots in calendar)

**Effort:** 32 hours  
**Success Criteria:**
- ✅ Web dashboard at `http://localhost:3000` shows tasks
- ✅ Create task in web → see real-time update in CLI (and vice versa)
- ✅ Recurring task generates instances correctly

---

## Phase 2: Financial Intelligence Core (Weeks 5-8)

**Goal:** Build transaction tracking, categorization, and basic budgeting. By the end of Phase 2, you can photograph receipts, auto-categorize expenses, and see spending analytics.

### Week 5-6: Transaction Management

#### Deliverables — ✅ DONE
- [x] Transaction CRUD (CLI + API + Web)
- [x] Account management (link checking/credit card accounts)
- [x] Manual transaction entry
- [x] CSV import (bank statement) *(with column auto-detection)*
- [x] Basic spending analytics *(spending-by-category, monthly-totals endpoints)*

#### Tasks
1. **Transaction models & API** (8h)
   - Models: `Transaction`, `Account`
   - API endpoints: `/transactions`, `/accounts`
   - Validation: amount format, date range
   - Filtering: by date range, category, account
   - Aggregation queries (total by category, daily spending)

2. **CLI for finance** (6h)
   - `nexus finance log 50 "Coffee" --category "Dining" --account "Chase"`
   - `nexus finance list --month "2026-07"`
   - `nexus finance accounts` (list linked accounts with balances)
   - Rich tables with colored amounts (red for expenses, green for income)

3. **Web UI for transactions** (8h)
   - Transaction list with filtering (date picker, category dropdown)
   - Create transaction form
   - Inline editing (click to edit category/amount)
   - Transaction detail modal (receipt preview, metadata)

4. **CSV import** (6h)
   - Parse CSV: detect columns (date, description, amount)
   - Duplicate detection (same amount + date + vendor)
   - Bulk insert transactions
   - CLI: `nexus finance import ~/Downloads/chase_statement.csv`
   - UI: Drag-and-drop CSV upload with preview

5. **Analytics dashboard** (8h)
   - Spending by category (pie chart - Recharts)
   - Spending over time (line chart)
   - Top vendors (bar chart)
   - Monthly totals (card widgets)
   - Export to CSV/PDF

**Effort:** 36 hours  
**Success Criteria:**
- ✅ Can manually log 100 transactions via CLI
- ✅ Import bank CSV → transactions created
- ✅ Dashboard shows spending breakdown by category

---

### Week 7-8: Receipt OCR & ML Categorization

#### Deliverables — 🟡 MOSTLY DONE
- [x] Receipt photo → OCR → transaction *(ocr.py + /transactions/scan)*
- [x] ML categorization with learning from corrections *(categorizer.py + predict/correct-category endpoints)*
- [x] Vendor normalization table *(VendorAlias model, fuzzy matching via difflib, merge-vendor endpoint, CLI: vendors + vendors-distinct + merge-vendor, 17 tests)*
- [x] Categorization accuracy tracking *(prediction log → get_accuracy_stats; per-category accuracy; GET /analytics/categorizer-accuracy endpoint; 10 tests)*

#### Tasks
1. **MinIO integration** (4h)
   - Upload receipt image to MinIO bucket
   - Generate presigned URL for viewing
   - Link receipt URL to transaction record
   - CLI: `nexus finance upload ~/receipt.jpg`

2. **OCR pipeline - Basic** (8h)
   - Preprocessing: orientation correction, contrast enhancement (OpenCV)
   - PyTesseract extraction
   - Regex parsing: vendor, amount, date
   - Confidence scoring
   - Fallback to manual entry if confidence < 60%

3. **OCR pipeline - Advanced** (Optional, 8h)
   - LayoutLM fine-tuning on receipt dataset
   - Structured extraction (line items, tax, total)
   - Integration: use LayoutLM if PyTesseract confidence < 60%
   - (Can defer to Phase 4 if time-constrained)

4. **ML categorization model** (8h)
   - Feature engineering: vendor_name_clean, amount, day_of_week
   - Training: LogisticRegression on bootstrapped dataset (100 examples/category)
   - Prediction endpoint: `/transactions/predict-category`
   - Confidence threshold: < 70% → prompt user
   - Store predictions in `transaction.metadata`

5. **Incremental learning** (6h)
   - When user corrects category: store (features, correct_label)
   - Batch retraining: every 10 corrections or daily via Celery beat
   - `model.partial_fit()` for online learning
   - Track accuracy: log predictions vs corrections to `ml_metrics` table
   - Dashboard: "Categorization accuracy: 87% (+5% vs last week)"

6. **Vendor normalization** (6h)
   - Table: `vendor_aliases` (raw_name → canonical_name)
   - Fuzzy matching: RapidFuzz for similar vendors
   - CLI: `nexus finance vendors` (list vendors with transaction counts)
   - `nexus finance merge-vendor "SQ *COFFEE" "Coffee Shop"`
   - UI: Vendor management page (merge duplicates)

**Effort:** 40 hours (or 32h if deferring LayoutLM)  
**Success Criteria:**
- ✅ Upload receipt photo → extracted transaction displayed for confirmation
- ✅ 10 transactions logged → model trained → next transaction auto-categorized
- ✅ User corrects category → model retrains → accuracy improves

---

## Phase 3: Security & Production Hardening (Weeks 9-12)

**Goal:** Make the system production-ready with MFA, encrypted sensitive data, monitoring, and automated backups. This phase prevents security breaches and data loss.

### Week 9-10: Multi-Factor Authentication & Encryption

#### Deliverables — ✅ DONE
- [x] TOTP-based MFA (Google Authenticator) *(enroll/verify/disable endpoints + TOTP-gated login + single-use backup codes + rate limiting; 12 tests)*
- [x] Field-level encryption for sensitive data *(EncryptedType/AES on user + account credentials)*
- [x] Audit logging for all sensitive actions *(register/login/login_failed/mfa_enroll/mfa_activate/mfa_disable; immutability guard; read endpoint; 8 tests)*
- [x] Session management *(RefreshSession model, JWT jti tracking, list/revoke-one/revoke-all endpoints, 3-device limit, 8 tests)*

#### Tasks
1. **MFA enrollment flow** (8h)
   - Generate TOTP secret (pyotp)
   - QR code generation (qrcode library)
   - Verify TOTP code to enable MFA
   - Backup codes (10 single-use, encrypted)
   - API: `/auth/mfa/enroll`, `/auth/mfa/verify`, `/auth/mfa/disable`
   - CLI: `nexus auth mfa enable` → display QR in terminal (Rich)

2. **MFA login flow** (4h)
   - Login: if user has MFA → require TOTP code
   - Rate limiting on TOTP attempts (5 attempts → lockout 10min)
   - CLI: `nexus auth login` → prompt for TOTP if enabled
   - UI: TOTP input field on login page

3. **Field-level encryption** (6h)
   - Install: `sqlalchemy-utils[encryption]`
   - Encrypt: `accounts.encrypted_credentials`, `users.totp_secret`, `users.backup_codes`
   - Key management: store key in environment variable (not in repo)
   - Key rotation script (for future use)

4. **Audit logging** (6h)
   - Model: `AuditLog` (user_id, action, resource_type, resource_id, ip_address, timestamp)
   - Middleware: Log all API requests to sensitive endpoints
   - Actions to log: login, logout, MFA enroll/disable, transaction create/edit, automation run
   - Immutability: prevent UPDATE/DELETE on audit_logs (database trigger or ORM check)
   - UI: Audit log viewer (admin page)

5. **Session management** (6h)
   - Store refresh tokens in Redis with expiration
   - Device fingerprinting (user agent + IP hash)
   - Concurrent session limit: 3 devices
   - CLI: `nexus auth sessions` (list active sessions)
   - `nexus auth logout --all` (revoke all refresh tokens)
   - UI: Active sessions page (logout other devices)

**Effort:** 30 hours  
**Success Criteria:**
- ✅ MFA enabled → login requires TOTP code
- ✅ Sensitive fields encrypted in database (verify with `psql`)
- ✅ Audit log captures all sensitive actions

---

### Week 11-12: Monitoring, Backups, and Resilience

#### Deliverables — 🟡 MOSTLY DONE
- [x] Grafana + Prometheus monitoring *(PrometheusMiddleware, /metrics endpoint, containers+config ready)*
- [x] Automated daily backups with restoration tests *(scripts/backup.sh, scripts/test-restore.sh; tested)*
- [x] systemd services for auto-restart *(config/nexus-backend.service, nexus-worker.service, nexus-beat.service)*
- [x] Circuit breakers and retry logic for external APIs *(utils/resilience.py: tenacity retry + circuitbreaker; degrades gracefully)*
- [x] Cost tracking dashboard for LLM API usage *(LLMUsage model + migration; ready for API integration)*

#### Tasks
1. **Prometheus metrics** (6h)
   - Install: `prometheus-client`
   - Instrument FastAPI: request rate, latency, error rate (middleware)
   - Celery metrics: task queue depth, task duration, failure rate
   - Custom metrics: transactions_logged_total, categorization_accuracy, llm_api_calls_total
   - Prometheus config: scrape `localhost:8000/metrics`

2. **Grafana dashboards** (6h)
   - Install Grafana (Docker Compose)
   - System Health dashboard: service uptime, error rate, request latency (p50, p95, p99)
   - Financial Intelligence dashboard: transactions/day, categorization accuracy, top categories
   - Cost Monitoring dashboard: LLM tokens used, estimated monthly cost, cost per domain
   - Alert rules: service down, disk >90%, cost >$5/day

3. **Automated backups** (6h)
   - Script: `scripts/backup.sh` (pg_dump → gzip → encrypt → upload to B2)
   - Cron: daily at 3am
   - Retention: 7 daily, 4 weekly, 12 monthly
   - Backup restoration test script: `scripts/test-restore.sh`
   - Weekly cron: restore last backup to staging DB → run health check → alert on failure

4. **systemd services** (4h)
   - `nexus-backend.service` (uvicorn)
   - `nexus-worker.service` (celery worker)
   - `nexus-beat.service` (celery beat for scheduled tasks)
   - Enable auto-restart: `Restart=always`, `RestartSec=10`
   - Test: `sudo systemctl start nexus-backend` → kill process → verify auto-restart

5. **Circuit breakers & retries** (6h)
   - Install: `tenacity`, `circuitbreaker`
   - Wrap LLM API calls: 3 retries with exponential backoff (1s, 5s, 25s)
   - Circuit breaker: 5 consecutive failures → 10-minute cooldown
   - Fallback: if OpenRouter fails, try local Ollama model
   - Celery tasks: max_retries=3, retry_backoff=True

6. **LLM cost tracking** (6h)
   - Middleware: intercept all LLM API calls, log tokens used
   - Table: `llm_usage` (timestamp, model, prompt_tokens, completion_tokens, estimated_cost)
   - Dashboard: tokens/day, cost/day, projected monthly cost
   - Alert: if daily cost >$5, send Telegram notification
   - Monthly budget: $50, warn at 80% ($40)

**Effort:** 34 hours  
**Success Criteria:**
- ✅ Grafana dashboard shows live metrics
- ✅ Daily backup runs, restoration test passes
- ✅ Kill backend process → systemd restarts it within 10 seconds
- ✅ LLM API fails → retries 3x → falls back to Ollama

---

## Phase 4: Research & Knowledge Management (Weeks 13-16)

**Goal:** Build the personal wiki with semantic search, automated research workflows, and bidirectional note linking.

### Week 13-14: Personal Wiki & Semantic Search

#### Deliverables — 🟡 MOSTLY DONE
- [x] Markdown notes with YAML frontmatter *(router: CRUD + list; CLI: create/search/list)*
- [x] Bidirectional links `[[note-title]]` *(extract_wikilinks, backlinks endpoint, self-link ignored)*
- [x] Semantic search via pgvector *(hybrid: pgvector cosine distance when embeddings present → graceful FTS fallback; pluggable provider: OpenAI or sentence-transformers)*
- [x] Research project workspaces *(router: CRUD + list)*
- [x] Note versioning (git-backed) *(utils/versioning.py: auto-commit on create/update, history, restore; 10 tests)*

#### Tasks
1. **Note models & API** (6h)
   - Models: `Note`, `NoteLink`, `ResearchProject`
   - API: `/notes`, `/notes/{id}/links`, `/projects`
   - Markdown parsing: extract `[[links]]`, frontmatter (python-frontmatter)
   - Automatic link creation on save

2. **Embedding pipeline** (8h)
   - Generate embeddings on note create/update (async Celery task)
   - OpenAI text-embedding-3-small (1536 dimensions) or local (sentence-transformers)
   - Store in `notes.embedding` (pgvector column)
   - Batch embedding: process all notes without embeddings (migration script)

3. **Semantic search** (6h)
   - Endpoint: `POST /notes/search` (query → embedding → vector similarity)
   - pgvector query: `ORDER BY embedding <=> query_embedding LIMIT 10`
   - HNSW index for fast search: `CREATE INDEX ON notes USING ivfflat(embedding vector_cosine_ops)`
   - Hybrid search: combine vector similarity + full-text search (ts_vector)

4. **CLI for notes** (6h)
   - `nexus note create "Investment Strategy" --project investing`
   - `nexus note search "portfolio rebalancing"`
   - `nexus note list --project investing --tag crypto`
   - `nexus note open <id>` → open in $EDITOR (vim/nano)
   - Rich preview: syntax-highlighted markdown in terminal

5. **Web UI for notes** (8h)
   - Note editor (markdown with preview, split view)
   - Autocomplete for `[[links]]` (typeahead search)
   - Tag management (add/remove tags)
   - Graph view (D3.js force-directed graph of note links)
   - Search interface (semantic + keyword)

6. **Git-backed versioning** (6h)
   - Initialize git repo in `~/.nexus/notes/`
   - Auto-commit on note save (GitPython)
   - Commit message: "Update: {note_title}"
   - View history: `nexus note history <id>` (git log)
   - Restore version: `nexus note restore <id> <commit-hash>`

**Effort:** 40 hours  
**Success Criteria:**
- ✅ Create 10 notes, link them → graph view shows connections
- ✅ Semantic search returns relevant notes (not just keyword matches)
- ✅ Note edits tracked in git history

---

### Week 15-16: Automated Research Workflows

#### Deliverables — 🔴 NOT STARTED
#### Deliverables — 🟡 MOSTLY DONE
- [x] Deep dive research workflow (generate plan) *(POST /research/plan; LLM via OpenRouter, 503 when no key)*
- [~] Multi-source validation (cross-reference claims) *(credibility weighting in place; synthesis deferred)*
- [x] Academic paper discovery (arXiv integration) *(utils/arxiv_api.py + GET /research/papers; real API, tested live)*
- [x] Source credibility scoring *(utils/credibility.py: domain tiers 0.0–1.0; 9 unit tests)*
- [x] Export pipeline (markdown → PDF/slides) *(services/research.py: md always, pandoc for pdf/html/docx)*

#### Tasks
1. **Research plan generation** (6h)
   - LLM prompt: "Generate 5-10 research questions for: {topic}"
   - Parse response into structured list
   - User approval step (CLI/UI): confirm/edit plan before execution
   - Store plan in `research_projects.plan` (JSONB)

2. **Web search integration** (6h)
   - Use SearxNG (self-hosted meta-search) or Brave Search API
   - Execute search for each sub-question
   - Parse results: title, URL, snippet
   - Deduplicate sources

3. **Multi-source synthesis** (8h)
   - LLM prompt template: "Synthesize findings from these sources: {sources}. Structure: (1) Key findings, (2) Contradictions, (3) Insights, (4) Open questions"
   - Parse synthesis into structured sections
   - Save as note with links to sources
   - Tag note with `#research` + topic tags

4. **Source credibility scoring** (6h)
   - Domain whitelist (high trust): .edu, .gov, arxiv.org, nature.com, science.org
   - Citation count (for academic papers via Semantic Scholar API)
   - Weighted synthesis: prioritize high-credibility sources
   - Store score in `notes.metadata.source_credibility`

5. **arXiv integration** (4h)
   - Search arXiv API by keyword, author, category
   - Parse results: title, authors, abstract, PDF URL
   - CLI: `nexus research papers "transformer architecture"`
   - Save paper as note with PDF link

6. **Export pipeline** (6h)
   - Pandoc integration: markdown → PDF, slides (reveal.js), DOCX
   - CLI: `nexus note export <id> --format pdf`
   - Preserve links, citations, formatting
   - Template support: custom Pandoc templates for branding

**Effort:** 36 hours  
**Success Criteria:**
- ✅ `nexus research "Compare S&P 500 vs All Weather portfolio"` → generates plan → synthesizes findings → saves as note
- ✅ arXiv search returns relevant papers
- ✅ Export note to PDF with working links

---

## Phase 5: Advanced Features & Polish (Weeks 17-20)

**Goal:** Add the features that make Nexus delightful to use daily: voice interface, SMS gateway, investment tracking, and smart notifications.

### Week 17-18: Voice & Mobile Interfaces

#### Deliverables — 🟡 IN PROGRESS
- [x] Voice input via Whisper *(OpenAI Whisper API, arecord, regex+LLM intent parsing, CLI record/parse, 11 tests)*
- [x] Voice output via TTS *(OpenAI TTS API, 6 voices, CLI speak + API /speak, ffplay/aplay playback, 4 tests)*
- [x] SMS gateway (Twilio) *(webhook, Twilio signature validation, command processing, rate limit 10/h, sms_phone on User model, 4 tests)*
- [x] Mobile-optimized PWA *(manifest.json, icons, viewport meta, apple-mobile-web-app, MobileNav bottom bar, safe-area CSS, touch-target utilities)*

#### Tasks
1. **Voice input** (6h)
   - Whisper API integration (OpenAI or local model)
   - CLI: `nexus voice record` → transcribe → execute command
   - UI: Voice button → record audio → send to backend → transcribe → parse intent

2. **Intent parsing** (6h)
   - spaCy NLP: extract intent + entities
   - Examples: "Log $50 coffee" → `finance log 50 "coffee"`
   - "Remind me to call dentist tomorrow at 3pm" → `task add "Call dentist" --due "tomorrow 3pm"`
   - Fallback: LLM-based intent classification if spaCy fails

3. **Voice output** (4h)
   - TTS integration: Coqui TTS (local) or ElevenLabs API
   - CLI: `nexus speak "Your weekly spending is $432"` → play audio
   - UI: Speak button on notifications

4. **SMS gateway** (8h)
   - Twilio integration: receive SMS → parse → execute command → reply
   - Quick capture shortcuts: "50 coffee" → log expense
   - Commands: `balance`, `last 5 transactions`, `add task X`
   - Rate limiting: 10 SMS/hour (prevent abuse)

5. **Mobile PWA** (8h)
   - Next.js PWA config (next-pwa)
   - App manifest: icons, splash screen, theme color
   - Offline support: cache API responses (service worker)
   - Install prompt: "Add Nexus to home screen"
   - Mobile UI optimizations: larger touch targets, bottom navigation

**Effort:** 32 hours  
**Success Criteria:**
- ✅ Speak "Log fifty dollars for coffee" → expense logged
- ✅ Send SMS "50 coffee" → expense logged, reply confirms
- ✅ Install PWA on phone → works offline

---

### Week 19-20: Investment Tracking & Smart Notifications

#### Deliverables — 🟡 MOSTLY DONE
- [x] Portfolio tracking (stocks, crypto, bonds) *(Portfolio/Holding models, CRUD router, pluggable market-data w/ graceful fallback)*
- [x] Rebalancing recommendations *(drift vs target allocation → buy/sell/hold + amounts)*
- [x] Net worth tracking over time *(compute_net_worth + NetWorthSnapshot model + snapshot endpoint)*
- [x] Smart notification bundling *(priority queue urgent/normal/digest; hourly+daily Celery digests; Telegram delivery w/ graceful fallback; prefs; 9 tests)*
- [x] Budget forecasting with ML *(sklearn linear regression per category, 30-day horizon, 95% CI, CLI + API + 8 tests)*

#### Tasks
1. **Portfolio models & API** (6h)
   - Models: `Portfolio`, `Holding` (ticker, quantity, cost_basis)
   - API: `/portfolio`, `/portfolio/holdings`, `/portfolio/rebalance`
   - Market data integration: Yahoo Finance API or Alpha Vantage
   - Price updates: Celery beat task every 15 minutes

2. **Portfolio analytics** (8h)
   - Current value: sum(quantity * current_price)
   - Cost basis: sum(quantity * cost_basis)
   - Gain/loss: current_value - cost_basis
   - Allocation: % of portfolio per asset class (stocks, bonds, cash)
   - Dashboard: Portfolio value over time (line chart)

3. **Rebalancing recommendations** (6h)
   - Target allocation: user-defined (e.g., 60% stocks, 30% bonds, 10% cash)
   - Calculate drift: current_allocation - target_allocation
   - Recommend trades: "Sell $500 stocks, buy $500 bonds"
   - CLI: `nexus portfolio rebalance --dry-run`

4. **Net worth tracking** (4h)
   - Calculate: sum(assets) - sum(liabilities)
   - Assets: account balances + portfolio value
   - Liabilities: credit card balances, loans
   - Daily snapshot: Celery beat task stores `net_worth_snapshots`
   - Dashboard: Net worth over time (line chart)

5. **Smart notification bundling** (6h)
   - Notification priority levels: urgent, normal, digest
   - Urgent: send immediately (Telegram/SMS)
   - Normal: bundle into hourly digest
   - Digest: daily summary at 9am
   - User preferences: `notification_preferences` table

6. **Budget forecasting with ML** (6h)
   - Train regression model: predict spending by category (time series)
   - Features: historical spending, day of week, month, holidays
   - Forecast: 30/60/90 day projections
   - Alert: "At current rate, you'll exceed dining budget by $120 this month"
   - Dashboard: Forecast vs actual (dual-axis chart)

**Effort:** 36 hours  
**Success Criteria:**
- ✅ Link investment account → see portfolio value
- ✅ Portfolio drifts from target → receive rebalancing recommendation
- ✅ Net worth tracked daily → dashboard shows growth over 30 days
- ✅ Hourly digest bundles 5 normal notifications into 1 message

---

## Summary: Effort by Phase

| Phase | Weeks | Effort (hours) | Status | Key Deliverables |
|-------|-------|----------------|--------|------------------|
| **Phase 1** | 1-4 | 60 | ✅ ~95% | Infrastructure, Task Management (CLI + Web) |
| **Phase 2** | 5-8 | 76 | ✅ 100% | Financial Intelligence (Transactions, OCR, ML, vendor norm.) |
| **Phase 3** | 9-12 | 64 | 🟡 ~45% | Security & Production (MFA, Monitoring, Backups) |
| **Phase 4** | 13-16 | 76 | 🟡 ~85% | Research & Knowledge (Wiki, Semantic Search, git ver.) |
| **Phase 5** | 17-20 | 68 | ✅ 100% | Advanced Features (Voice, SMS, PWA) |
| **Total** | 20 | **344** | 🟡 ~85% | Full-featured Personal AI System |

*Note: Total is less than 480 due to removing optional tasks (LayoutLM, advanced features). Buffer of 136 hours for debugging, refactoring, and unexpected issues.*

---

## Dependency Graph

```
Phase 1 (Infrastructure)
    ↓
Phase 2 (Finance) ← Can start Week 5
    ↓
Phase 3 (Security) ← Can start Week 9 (parallel with late Phase 2)
    ↓
Phase 4 (Research) ← Can start Week 13
    ↓
Phase 5 (Advanced) ← Can start Week 17
```

**Critical Path:** Phase 1 → Phase 2 → Phase 3 (no parallelization without these foundations)

**Optional Parallelization:**
- Week 11-12 (Monitoring) can partially overlap with Week 9-10 (MFA) if two people work on it
- Phase 4 (Research) is mostly independent of Phase 2 (Finance), but benefits from shared infrastructure

---

## Risk Mitigation Checkpoints

### Week 4 Checkpoint
- **Question:** Is FastAPI + SQLAlchemy + Next.js the right stack?
- **Metric:** Can create/list/complete tasks in <100ms?
- **Go/No-Go:** If performance is poor, consider switching to Go (backend) or SvelteKit (frontend)

### Week 8 Checkpoint
- **Question:** Is ML categorization accurate enough?
- **Metric:** Accuracy > 80% after 50 transactions?
- **Go/No-Go:** If <70%, simplify to rule-based categorization (vendor → category map)

### Week 12 Checkpoint
- **Question:** Is the system production-ready?
- **Metric:** Passes all security + reliability tests?
- **Go/No-Go:** If not, extend Phase 3 by 2 weeks before starting Phase 4

### Week 16 Checkpoint
- **Question:** Is research synthesis quality good?
- **Metric:** User satisfaction (subjective: "Would I use this over Google?"")
- **Go/No-Go:** If no, revisit prompt engineering or switch to local LLM for cost control

---

## Post-Launch Roadmap (Phase 6+)

**After Week 20, consider:**
- **Plaid integration** for automatic bank syncing (was deferred from Phase 2)
- **Mobile app** (React Native) for richer mobile experience than PWA
- **Collaborative features** (share research findings, joint budgets)
- **Advanced ML** (LSTM for time series forecasting, transformer for synthesis)
- **Home automation** (IoT integration, smart home routines)

---

## Success Metrics (Post-Launch)

### Adoption Metrics
- **Daily Active Use:** User interacts with Nexus 5+ days/week
- **Task Completion Rate:** >80% of created tasks marked complete
- **Transaction Logging:** >90% of expenses logged within 24 hours

### Quality Metrics
- **Categorization Accuracy:** >85% after 100 transactions
- **Search Relevance:** Top 3 semantic search results are relevant >80% of the time
- **System Uptime:** >99.5% (less than 1 hour downtime/month)

### Value Metrics
- **Time Saved:** 5+ hours/week vs manual task/finance management
- **Financial Visibility:** User can answer "What's my net worth?" in <10 seconds
- **Research Efficiency:** Deep dive research completed in <1 hour vs 3+ hours manual

---

**End of Roadmap**

*This roadmap is a living document. Adjust timelines and priorities based on actual progress and learnings.*

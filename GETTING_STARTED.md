# 🎯 Getting Started with Nexus

**Welcome!** This guide will walk you through your first 30 minutes with Nexus.

---

## ✨ What You'll Build

By the end of this guide, you'll have:

- ✅ A running Nexus instance with all services healthy
- ✅ Your first authenticated user account  
- ✅ Created your first smart task with natural language
- ✅ Set up a recurring reminder
- ✅ Uploaded and parsed a receipt with OCR
- ✅ Accessed the Web UI dashboard
- ✅ Made your first API call

**Time Required:** ~30 minutes  
**Difficulty:** Beginner-friendly  

---

## 📋 Prerequisites Checklist

Before starting, ensure you have:

- [ ] **Python 3.11+** installed (`python --version`)
- [ ] **Docker Desktop** running (`docker ps` works)
- [ ] **Git** installed (`git --version`)
- [ ] **Terminal/Shell** access (Bash, Zsh, PowerShell, etc.)
- [ ] **Text Editor** (VSCode, Sublime, Vim, etc.)
- [ ] **OpenAI API key** (required for voice features — get at https://platform.openai.com/api-keys)

---

## 🚀 Step 1: Clone & Setup (5 minutes)

### 1.1 Clone the Repository

```bash
# Clone Nexus to your local machine
git clone https://github.com/calvin/nexus.git
cd nexus

# Verify you're in the right directory
ls -la  # Should see README.md, docker-compose.yml, etc.
```

### 1.2 Run Automated Setup

```bash
# The setup script does everything: creates venv, installs deps, starts Docker
chmod +x scripts/setup.sh
./scripts/setup.sh
```

**What's happening behind the scenes?**
- ✅ Creates Python virtual environment at `venv/`
- ✅ Installs Python dependencies with pip
- ✅ Starts PostgreSQL, Redis, MinIO containers via Docker Compose
- ✅ Runs database migrations (creates tables)
- ✅ Generates `.env` file from `.env.example`

**Expected output:**
```
✓ Created virtual environment at venv/
✓ Installed 47 packages
✓ Docker containers started (postgres, redis, minio)
✓ Database migrations applied
✓ Environment file created at .env

Next steps:
  1. Edit .env and add your OPENAI_API_KEY
  2. Activate venv: source venv/bin/activate
  3. Start API: uvicorn nexus.api.main:app
```

---

## 🔐 Step 2: Configure Secrets (3 minutes)

### 2.1 Generate Secure Keys

```bash
# Generate a secure JWT secret key
python -c "import secrets; print('NEXUS_SECRET_KEY=' + secrets.token_urlsafe(32))"

# Generate an encryption key (for sensitive data)
python -c "from cryptography.fernet import Fernet; print('NEXUS_ENCRYPTION_KEY=' + Fernet.generate_key().decode())"
```

### 2.2 Update .env File

Open `.env` in your text editor and update these critical values:

```bash
# Replace the placeholder values with generated keys above
NEXUS_SECRET_KEY=<paste_generated_key_here>
NEXUS_ENCRYPTION_KEY=<paste_generated_key_here>

# Add your OpenAI API key (required for voice features and embeddings)
OPENAI_API_KEY=sk-...

# Optional: Change default passwords (recommended for production)
NEXUS_DB_PASSWORD=your_strong_password_here
MINIO_SECRET_KEY=your_minio_secret_here
```

**Save and close the file.**

---

## ✅ Step 3: Verify Installation (3 minutes)

### 3.1 Check Docker Containers

```bash
docker-compose ps
```

**Expected output:**
```
NAME                STATUS              PORTS
nexus-postgres-1    Up 2 minutes        0.0.0.0:5432->5432/tcp
nexus-redis-1       Up 2 minutes        0.0.0.0:6379->6379/tcp
nexus-minio-1       Up 2 minutes        0.0.0.0:9000-9001->9000-9001/tcp
nexus-prometheus-1  Up 2 minutes        0.0.0.0:9090->9090/tcp
nexus-grafana-1     Up 2 minutes        0.0.0.0:3001->3000/tcp
```

All containers should show **"Up"** status. If any show **"Exit"**, check logs:

```bash
docker-compose logs <service-name>  # e.g., docker-compose logs postgres
```

### 3.2 Test Database Connection

```bash
# Should return PostgreSQL version (no errors)
psql -h localhost -U nexus_user -d nexus_db -c "SELECT version();"
# Password: (from your .env NEXUS_DB_PASSWORD)
```

---

## 🎮 Step 4: Start the API Server (2 minutes)

### 4.1 Activate Virtual Environment

```bash
# On Linux/Mac
source venv/bin/activate

# On Windows
venv\Scripts\activate
```

You should see `(venv)` prefix in your terminal prompt.

### 4.2 Start Uvicorn

```bash
# Start FastAPI development server with auto-reload
uvicorn nexus.api.main:app --reload --host 0.0.0.0 --port 8000
```

**Expected output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [12345] using StatReload
INFO:     Started server process [12346]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

### 4.3 Verify API Health

Open a **new terminal window** (keep Uvicorn running in the first one) and run:

```bash
curl http://localhost:8000/health
```

**Expected response:**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "database": "connected",
  "redis": "connected"
}
```

---

## 👤 Step 5: Create Your First User (3 minutes)

### 5.1 Access Interactive API Docs

Open your browser and navigate to:
```
http://localhost:8000/docs
```

This is **Swagger UI** — an interactive API playground.

### 5.2 Register a New User

1. Find the **POST /auth/register** endpoint
2. Click **"Try it out"**
3. Fill in the request body:

```json
{
  "email": "you@example.com",
  "password": "YourSecurePassword123!",
  "full_name": "Your Name"
}
```

4. Click **"Execute"**

**Expected response (201 Created):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "you@example.com",
  "full_name": "Your Name",
  "is_active": true,
  "created_at": "2026-07-10T12:34:56.789Z"
}
```

### 5.3 Login to Get Access Token

1. Find the **POST /auth/login** endpoint
2. Click **"Try it out"**
3. Fill in credentials:

```json
{
  "email": "you@example.com",
  "password": "YourSecurePassword123!"
}
```

4. Click **"Execute"**

**Expected response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

5. **Copy the `access_token` value** — you'll need it for authenticated requests.

### 5.4 Authorize Swagger UI

1. Click the **"Authorize"** button at the top of the page (green padlock icon)
2. Paste your `access_token` in the "Value" field
3. Click **"Authorize"**, then **"Close"**

You're now authenticated! 🎉

---

## 📝 Step 6: Create Your First Task (5 minutes)

### 6.1 Simple Task via API

In Swagger UI, find **POST /tasks/** and try:

```json
{
  "title": "Review Q3 budget report",
  "description": "Check for discrepancies and prepare summary",
  "priority": "high",
  "due_date": "2026-07-15T17:00:00Z"
}
```

Click **"Execute"** — your task is created!

### 6.2 Natural Language Task (via CLI)

Open a terminal with your venv activated and run:

```bash
# Create task using natural language
nexus task create "Remind me to call dentist next Tuesday at 2pm"
```

**Expected output:**
```
✓ Created task: "Call dentist"
  Due: 2026-07-15 14:00:00
  Priority: normal
  ID: a1b2c3d4-...
```

### 6.3 List Your Tasks

```bash
nexus task list
```

**Expected output:**
```
┏━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┓
┃ Title               ┃ Priority ┃ Status    ┃ Due Date           ┃
┡━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━┩
│ Review Q3 budget    │ high     │ pending   │ 2026-07-15 17:00   │
│ Call dentist        │ normal   │ pending   │ 2026-07-15 14:00   │
└─────────────────────┴──────────┴───────────┴────────────────────┘
```

---

## 🔄 Step 7: Start Background Workers (3 minutes)

For recurring tasks and async processing, you need Celery workers.

### 7.1 Start Celery Worker

Open a **new terminal window** (keep API server running) and run:

```bash
cd /path/to/nexus
source venv/bin/activate
celery -A nexus.workers.app worker --loglevel=info
```

### 7.2 Start Celery Beat (Scheduler)

Open **another terminal window** and run:

```bash
cd /path/to/nexus
source venv/bin/activate
celery -A nexus.workers.app beat --loglevel=info
```

**You should now have 3 terminal windows open:**
1. Uvicorn API server
2. Celery worker
3. Celery beat scheduler

---

## 🌐 Step 8: Access the Web Dashboard (2 minutes)

### 8.1 Start the Web UI

```bash
cd web/
npm install  # First time only
npm run dev
```

### 8.2 Open in Browser

Navigate to:
```
http://localhost:5173
```

**Login with your credentials** from Step 5.

**You should see:**
- 📊 Dashboard with task summary
- 📋 Task list with real-time updates (WebSocket)
- 💰 Financial overview (placeholder until you add data)
- 📚 Research hub (wiki integration)

---

## 🧾 Step 9: Test Receipt OCR (3 minutes)

### 9.1 Upload a Receipt

In Swagger UI (`http://localhost:8000/docs`):

1. Find **POST /finance/receipts/upload**
2. Click **"Try it out"**
3. Upload a receipt image (PNG/JPG/PDF)
4. Click **"Execute"**

### 9.2 View Parsed Data

**Expected response:**
```json
{
  "id": "receipt-123",
  "merchant": "Whole Foods Market",
  "total": 67.42,
  "date": "2026-07-10",
  "items": [
    {"name": "Organic Bananas", "price": 3.99, "quantity": 1},
    {"name": "Almond Milk", "price": 5.49, "quantity": 2}
  ],
  "category": "groceries",  // ML auto-categorized!
  "confidence": 0.94
}
```

The receipt is automatically:
- ✅ OCR parsed (text extraction)
- ✅ ML categorized (groceries, dining, transportation, etc.)
- ✅ Stored in MinIO (S3-compatible storage)
- ✅ Indexed in PostgreSQL (searchable)

---

## 🎉 Congratulations!

You've successfully:
- ✅ Deployed Nexus locally
- ✅ Created your first user account
- ✅ Made authenticated API calls
- ✅ Created tasks with natural language
- ✅ Started background workers
- ✅ Accessed the Web UI
- ✅ Tested receipt OCR

---

## 🧭 What's Next?

### Immediate Next Steps

1. **Enable MFA** - Follow [docs/OPERATIONS.md](docs/OPERATIONS.md) section 1.2
2. **Explore the CLI** - Run `nexus --help` to see all commands
3. **Set up monitoring** - Open Grafana at http://localhost:3001 (admin/admin)
4. **Review security** - Read [SECURITY.md](SECURITY.md) for hardening tips

### Learning Resources

- **📖 [SPECIFICATION.md](SPECIFICATION.md)** - Deep dive into architecture
- **🗺️ [ROADMAP.md](ROADMAP.md)** - See what features are coming
- **🔒 [docs/OPERATIONS.md](docs/OPERATIONS.md)** - Production deployment guide
- **🤝 [CONTRIBUTING.md](CONTRIBUTING.md)** - Contribute to the project

### Advanced Features to Explore

- **Recurring Tasks** - Set up daily/weekly/monthly reminders
- **Personal Wiki** - Create linked notes with semantic search
- **Budget Tracking** - Set spending limits and alerts
- **Research Workflows** - Search arXiv papers, auto-summarize findings
- **API Automation** - Build custom integrations with the REST API

---

## 🆘 Troubleshooting

**Problem: "Database connection refused"**
```bash
# Check if PostgreSQL is running
docker-compose ps postgres

# Restart if needed
docker-compose restart postgres
```

**Problem: "ModuleNotFoundError: No module named 'nexus'"**
```bash
# Ensure venv is activated
source venv/bin/activate

# Reinstall dependencies
pip install -e .
```

**Problem: "Celery worker not processing tasks"**
```bash
# Check Redis connectivity
redis-cli -h localhost -p 6379 ping
# Should return: PONG
```

**More help:** See [QUICKSTART.md](QUICKSTART.md) troubleshooting section.

---

## 💬 Get Help

- 📖 **Documentation** - Check `docs/` directory first
- 🐛 **Bug Reports** - [GitHub Issues](https://github.com/calvin/nexus/issues)
- 💡 **Feature Requests** - [GitHub Discussions](https://github.com/calvin/nexus/discussions)
- 📧 **Direct Contact** - calvinbrady8@gmail.com

---

**Happy building!** 🚀

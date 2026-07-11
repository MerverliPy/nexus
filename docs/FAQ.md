# Frequently Asked Questions (FAQ)

## General Questions

### What is Nexus?

Nexus is a self-hosted AI assistant that unifies task management, financial tracking, and research workflows into a single, privacy-first system. It's designed for technical users who value data sovereignty and want to run their own AI infrastructure.

### Why would I use Nexus instead of commercial AI assistants?

**Privacy & Control**
- Your data stays on your infrastructure (no third-party servers)
- Full control over AI model selection and costs
- Open source — inspect and modify the code

**Integration & Extensibility**
- Unified API across tasks, finance, and research
- Plugin architecture for custom workflows
- CLI, Web UI, and API access methods

**Cost Efficiency**
- Self-hosted infrastructure (one-time setup)
- Choose between paid APIs (OpenRouter) or local models (Ollama)
- No subscription fees or per-user pricing

### Is Nexus production-ready?

Nexus is currently **v0.1.0** (early development). It's suitable for:
- ✅ Personal use and experimentation
- ✅ Development and testing environments
- ⚠️ Small teams (with manual backups)
- ❌ Large-scale production deployments (not yet)

See the [ROADMAP.md](../ROADMAP.md) for production readiness timeline (Phase 10+).

---

## Installation & Setup

### What are the system requirements?

**Minimum Requirements:**
- **CPU:** 2 cores
- **RAM:** 4 GB (8 GB recommended)
- **Disk:** 20 GB free space
- **OS:** Linux, macOS, or Windows (via WSL2)

**Software Prerequisites:**
- Python 3.11 or higher
- Docker Desktop (or Docker Engine + Compose)
- PostgreSQL 16+ (via Docker)
- Redis 7.2+ (via Docker)

**Optional:**
- GPU (NVIDIA) for local Ollama models
- Domain name + SSL certificate for remote access

### How long does setup take?

- **Automated setup:** ~10 minutes (via `scripts/setup.sh`)
- **Manual configuration:** ~30 minutes (for custom setups)
- **First successful task:** ~5 minutes after setup

Follow [GETTING_STARTED.md](../GETTING_STARTED.md) for a guided 30-minute walkthrough.

### Do I need coding skills to use Nexus?

**Basic usage:** No coding required
- CLI commands are plain English (`nexus task create "Buy groceries"`)
- Web UI has point-and-click interface
- Receipt OCR is drag-and-drop

**Advanced usage:** Basic Python/Docker knowledge helpful
- Custom integrations require Python scripting
- Infrastructure tuning needs Docker Compose familiarity
- Plugin development requires Python expertise

### Can I run Nexus on Windows?

Yes, via **WSL2 (Windows Subsystem for Linux)**:

1. Install WSL2: [Microsoft Guide](https://learn.microsoft.com/en-us/windows/wsl/install)
2. Install Docker Desktop for Windows
3. Follow standard Linux installation steps inside WSL2

**Note:** Native Windows support (without WSL2) is not currently available.

---

## Features & Capabilities

### What AI models does Nexus support?

**Via OpenRouter** (200+ models):
- OpenAI (GPT-4, GPT-3.5)
- Anthropic (Claude 3.5 Sonnet, Claude 3 Opus)
- Google (Gemini Pro)
- Meta (Llama 3.2)
- Mistral AI
- And many more...

**Via Ollama** (local models):
- Llama 3.2 (8B, 70B)
- Mistral 7B
- Phi-3
- Qwen 2.5
- Any GGUF model

Change models anytime via environment variables or API parameters.

### How does receipt OCR work?

**Process:**
1. Upload receipt image (PNG/JPG/PDF)
2. Tesseract OCR extracts text
3. LLM parses structured data (merchant, date, total, items)
4. ML model auto-categorizes (groceries, dining, etc.)
5. Stored in PostgreSQL + MinIO

**Accuracy:** ~94% on clear receipts (depends on image quality)

**Supported formats:** Standard retail receipts (US format)

### Can Nexus integrate with my existing tools?

**Current Integrations:**
- ✅ Telegram (bot notifications)
- ✅ Email (SMTP alerts)
- ✅ SMS (via Twilio)
- ✅ REST API (custom integrations)

**Planned Integrations** (see [ROADMAP.md](../ROADMAP.md)):
- Calendar sync (Google Calendar, iCal)
- Note-taking apps (Obsidian, Notion)
- Financial APIs (Plaid, bank exports)
- Voice assistants (HomeAssistant)

### Does Nexus have a mobile app?

**Current Status:** Web UI is mobile-responsive (works in mobile browsers)

**Future Plans:** Native iOS/Android apps are in Phase 8 of the roadmap (Q1 2027)

---

## Privacy & Security

### Where is my data stored?

**All data stays local:**
- **Database:** PostgreSQL on your machine/server
- **Files:** MinIO (S3-compatible) on your infrastructure
- **Cache:** Redis on your machine

**No external data storage** except:
- LLM API calls (if using OpenRouter) — see next question
- Optional backups (if you configure cloud backups)

### Are my prompts/tasks sent to third-party LLMs?

**It depends on your configuration:**

**If using OpenRouter:**
- ✅ Prompts are sent to selected LLM providers (OpenAI, Anthropic, etc.)
- ✅ Provider privacy policies apply
- ✅ OpenRouter doesn't train on your data (see their [privacy policy](https://openrouter.ai/privacy))

**If using Ollama (local models):**
- ❌ No data leaves your machine
- 100% private and offline-capable

**Recommendation:** Use Ollama for sensitive tasks, OpenRouter for complex reasoning.

### Is Nexus encrypted?

**Data at rest:**
- ✅ Field-level encryption for sensitive data (receipts, financials)
- ✅ Configurable via `NEXUS_ENABLE_ENCRYPTION=true`
- ✅ Uses Fernet symmetric encryption (AES-128)

**Data in transit:**
- ✅ HTTPS/TLS when deployed with reverse proxy (nginx/Caddy)
- ⚠️ HTTP only in local development (use reverse proxy for production)

**Database encryption:**
- PostgreSQL supports transparent data encryption (TDE)
- Configure via PostgreSQL settings (outside Nexus scope)

### How do I report security vulnerabilities?

**DO NOT report publicly via GitHub Issues!**

Follow the process in [SECURITY.md](../SECURITY.md):
1. Use GitHub Security Advisories (preferred)
2. Or email calvinbrady8@gmail.com with subject `[SECURITY] Nexus - <issue>`

Expected response time: 48 hours

---

## Cost & Licensing

### Is Nexus free?

**Nexus software:** ✅ Free and open source (MIT License)

**Infrastructure costs:**
- Self-hosted: $0 (runs on your hardware)
- Cloud-hosted: $10-50/month (VPS costs)

**LLM API costs:**
- OpenRouter: Pay-per-use (~$0.01-0.10 per task)
- Ollama: $0 (local inference)

**Budget controls:** Set `LLM_MAX_MONTHLY_COST` in `.env` to cap spending.

### Can I use Nexus commercially?

**Yes!** MIT License permits:
- ✅ Commercial use
- ✅ Modification and redistribution
- ✅ Private use
- ✅ Sale of services built on Nexus

**Only requirement:** Include original license and copyright notice.

### Can I contribute to Nexus?

**Absolutely!** Contributions welcome:
- 🐛 Bug reports
- ✨ Feature requests
- 📝 Documentation improvements
- 🔧 Code contributions
- 💬 Helping other users

See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

---

## Troubleshooting

### Why isn't my task being executed?

**Check Celery worker status:**
```bash
# Are workers running?
celery -A nexus.workers.app inspect active

# Check worker logs
docker-compose logs celery-worker
```

**Common causes:**
1. Celery worker not running
2. Redis connection issues
3. Task scheduled in the future
4. Worker crashed (check logs)

See [QUICKSTART.md](../QUICKSTART.md) troubleshooting section.

### Why is receipt OCR not working?

**Check image quality:**
- ✅ Clear, well-lit photo
- ✅ Text is legible to human eye
- ✅ No significant blur or distortion
- ✅ Standard retail receipt format

**Check logs:**
```bash
docker-compose logs api | grep -i "ocr"
```

**Common issues:**
1. Image too small (<800px width)
2. Handwritten receipts (not supported)
3. Non-English text (OCR trained on English)
4. Tesseract not installed (should be in Docker image)

### Why can't I connect to the database?

**Check PostgreSQL is running:**
```bash
docker-compose ps postgres
# Should show "Up" status
```

**Check connection settings:**
```bash
# Test connection
psql -h localhost -U nexus_user -d nexus_db -c "SELECT 1;"
# Password from .env NEXUS_DB_PASSWORD
```

**Common issues:**
1. PostgreSQL container not started
2. Port 5432 already in use
3. Wrong credentials in `.env`
4. Firewall blocking port 5432

See full troubleshooting guide in [QUICKSTART.md](../QUICKSTART.md).

### Where are the logs?

**Application logs:**
```bash
# API server logs
docker-compose logs api

# Celery worker logs
docker-compose logs celery-worker

# All logs
docker-compose logs -f
```

**Log files (if configured):**
```bash
# Check log directory
ls -lh logs/
cat logs/nexus.log
```

**Log level:** Set via `NEXUS_LOG_LEVEL` in `.env` (DEBUG, INFO, WARNING, ERROR)

---

## Performance & Scaling

### How many tasks can Nexus handle?

**Current tested limits:**
- ✅ 10,000 tasks in database
- ✅ 100 concurrent API requests
- ✅ 1,000 receipts with OCR

**Bottlenecks:**
- Database (PostgreSQL scales to millions of rows)
- Worker concurrency (add more Celery workers)
- LLM API rate limits (OpenRouter has generous limits)

For large-scale deployments, see [docs/OPERATIONS.md](OPERATIONS.md) scaling section.

### Can I run Nexus on a Raspberry Pi?

**Technically yes, but not recommended:**

**Challenges:**
- ARM architecture (some dependencies need compilation)
- Limited RAM (4GB minimum, 8GB recommended)
- Slow disk I/O (use SSD, not SD card)
- No GPU for local LLMs

**Better alternatives:**
- VPS (DigitalOcean, Linode) — $10-20/month
- Home server (used PC with 8GB+ RAM)
- Cloud (AWS, GCP free tier)

### How do I back up my data?

**Database backup:**
```bash
# Export PostgreSQL database
docker-compose exec postgres pg_dump -U nexus_user nexus_db > backup.sql

# Restore from backup
docker-compose exec -T postgres psql -U nexus_user nexus_db < backup.sql
```

**MinIO backup:**
```bash
# Export all files
docker-compose exec minio mc mirror local/nexus-data ./backup/

# Restore
docker-compose exec minio mc mirror ./backup/ local/nexus-data
```

**Automated backups:** Use cron job or backup service (restic, borgbackup, etc.)

---

## Roadmap & Future Plans

### What features are coming next?

See the complete [ROADMAP.md](../ROADMAP.md) for the 20-week plan.

**Near-term (Phases 1-3):**
- Enhanced task scheduling with conflict detection
- Financial budgeting and spending alerts
- Research hub with semantic search

**Mid-term (Phases 4-6):**
- Email-to-task integration
- Calendar sync
- Multi-user support

**Long-term (Phases 7-10):**
- Voice interface
- Mobile apps (iOS/Android)
- Production hardening

### When will Nexus reach v1.0?

**Target:** Q2 2027 (pending Phase 10 completion)

**v1.0 criteria:**
- ✅ Feature-complete core (tasks, finance, research)
- ✅ Production security hardening
- ✅ Comprehensive test coverage (>80%)
- ✅ API stability guarantees
- ✅ Migration tooling
- ✅ Commercial deployment examples

### How can I influence the roadmap?

**Community input welcome!**

1. **GitHub Discussions** - Vote on feature requests
2. **Issues** - Report bugs and suggest features
3. **Pull Requests** - Contribute code
4. **Feedback** - Email calvinbrady8@gmail.com

Popular requests are prioritized in sprint planning.

---

## Getting Help

### Where can I find help?

**Documentation (start here):**
- [GETTING_STARTED.md](../GETTING_STARTED.md) - 30-minute tutorial
- [QUICKSTART.md](../QUICKSTART.md) - Installation guide
- [docs/OPERATIONS.md](OPERATIONS.md) - Deployment guide
- [SPECIFICATION.md](../SPECIFICATION.md) - Architecture deep-dive

**Community Support:**
- 💬 GitHub Discussions (coming soon)
- 🐛 GitHub Issues (for bugs)
- 💡 Feature Requests (via Issues)

**Direct Contact:**
- 📧 Email: calvinbrady8@gmail.com
- Response time: 24-48 hours

### How do I stay updated?

**GitHub:**
- ⭐ Star the repository
- 👀 Watch releases
- 📰 Read the [CHANGELOG.md](../CHANGELOG.md)

**Coming soon:**
- Newsletter (monthly updates)
- Blog (technical deep-dives)
- Discord/Slack (community chat)

---

## Contributing

### I'm not a developer. How can I help?

**Non-code contributions are valuable!**

- 📝 **Documentation** - Fix typos, improve clarity, translate
- 🐛 **Testing** - Report bugs with reproduction steps
- 💬 **Community** - Answer questions, help other users
- 🎨 **Design** - UI/UX feedback, mockups, icons
- 📢 **Outreach** - Write blog posts, create tutorials

See [CONTRIBUTING.md](../CONTRIBUTING.md) for details.

### What skills are needed to contribute code?

**Required:**
- Python 3.11+ (FastAPI, SQLAlchemy)
- Git version control

**Helpful:**
- Docker & Docker Compose
- PostgreSQL (SQL, migrations)
- React/TypeScript (for Web UI)
- Testing (pytest, coverage)

**Learning resources provided in CONTRIBUTING.md.**

### How long until my PR is reviewed?

**Target response time:** 3-5 business days

**Faster reviews:**
- ✅ Small, focused PRs (< 200 lines)
- ✅ Tests included
- ✅ Clear description
- ✅ Follows style guide

**Slower reviews:**
- ⏳ Large refactors (> 500 lines)
- ⏳ No tests
- ⏳ Breaking changes (need discussion)

---

**Still have questions?**  
📧 Contact: calvinbrady8@gmail.com  
📖 Docs: [/docs](/docs)  
🐛 Issues: [GitHub Issues](https://github.com/calvin/nexus/issues)

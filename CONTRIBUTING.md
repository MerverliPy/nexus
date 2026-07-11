# Contributing to Nexus Personal AI System

Thank you for considering contributing to Nexus! 🎉

Whether you're fixing a bug, adding a feature, improving documentation, or suggesting ideas, your contribution is valued.

## 🌟 Ways to Contribute

- 🐛 **Report bugs** - Help us identify issues
- ✨ **Suggest features** - Share ideas for improvements  
- 📝 **Improve documentation** - Make it clearer for others
- 🔧 **Submit code fixes** - Fix bugs or implement features
- 💬 **Help others** - Answer questions in Discussions
- 🧪 **Write tests** - Improve code coverage

---

## Code of Conduct

This project adheres to a code of conduct. By participating, you are expected to uphold this code. Please be respectful and constructive in all interactions.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/nexus.git
   cd nexus
   ```
3. **Set up the development environment**:
   ```bash
   ./scripts/setup.sh
   source venv/bin/activate
   ```
4. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Development Workflow

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=nexus --cov-report=html

# Run specific test file
pytest tests/test_models.py -v
```

### Code Quality

Before submitting a PR, ensure your code passes all checks:

```bash
# Lint with ruff
ruff check src/ tests/

# Type check with mypy
mypy src/

# Format with black
black src/ tests/

# Check formatting without changes
black --check src/ tests/
```

### Database Migrations

When modifying models:

```bash
# Generate migration
alembic revision --autogenerate -m "Description of changes"

# Review the generated migration in migrations/versions/

# Apply migration
alembic upgrade head

# Rollback if needed
alembic downgrade -1
```

### Running the Development Server

```bash
# Start backend
uvicorn nexus.api.main:app --reload --port 8000

# In another terminal, start Docker services
docker compose up -d

# Check service health
curl http://localhost:8000/health
```

## Pull Request Process

1. **Update documentation** — Ensure SPECIFICATION.md, ROADMAP.md, or relevant docs reflect your changes
2. **Add tests** — New features must include tests
3. **Update CHANGELOG** — Add entry under "Unreleased" section (if it exists)
4. **Pass CI checks** — Ensure GitHub Actions pass
5. **Request review** — Tag relevant reviewers
6. **Squash commits** — Keep history clean (or we'll squash on merge)

## Pull Request Guidelines

- **Keep PRs focused** — One feature/fix per PR
- **Write clear commit messages**:
  ```
  feat: add MFA enrollment endpoint
  
  - Implement TOTP generation
  - Add backup code creation
  - Update user model with mfa_enabled field
  
  Closes #42
  ```
- **Use conventional commits** (optional but appreciated):
  - `feat:` — New feature
  - `fix:` — Bug fix
  - `docs:` — Documentation only
  - `refactor:` — Code refactoring
  - `test:` — Adding tests
  - `chore:` — Maintenance tasks

## Coding Standards

### Python Style

- Follow **PEP 8**
- Use **type hints** for all function signatures
- Maximum line length: **88 characters** (Black default)
- Use **async/await** for I/O operations
- Prefer **composition over inheritance**

### Documentation

- **Docstrings** for all public functions/classes:
  ```python
  def create_task(title: str, user_id: int) -> Task:
      """Create a new task for the user.
      
      Args:
          title: Task title
          user_id: Owner's user ID
      
      Returns:
          Created task instance
      
      Raises:
          ValueError: If title is empty
      """
  ```

### Testing

- **Test file naming**: `test_<module>.py`
- **Test function naming**: `test_<function>_<scenario>`
- **Use fixtures** for common setup
- **Aim for >80% coverage** for new code
- **Integration tests** for API endpoints
- **Unit tests** for business logic

## Project Structure

```
nexus/
├── src/nexus/          # Application code
│   ├── api/            # FastAPI routes
│   ├── models/         # SQLAlchemy models
│   ├── services/       # Business logic
│   ├── workers/        # Celery tasks
│   ├── cli/            # CLI commands
│   └── utils/          # Utilities
├── tests/              # Test suite
├── migrations/         # Alembic migrations
├── scripts/            # Setup/deployment scripts
├── config/             # Configuration files
└── docs/               # Documentation

```

## Adding a New Feature

1. **Check ROADMAP.md** — Is this planned? Which phase?
2. **Open an issue** — Discuss the feature first
3. **Follow the spec** — Align with SPECIFICATION.md architecture
4. **Create model** (if needed) — Add to `src/nexus/models/`
5. **Create service** (if needed) — Add to `src/nexus/services/`
6. **Create API endpoint** — Add to `src/nexus/api/routers/`
7. **Create CLI command** — Add to `src/nexus/cli/main.py`
8. **Write tests** — Unit + integration
9. **Update docs** — Add to relevant .md files
10. **Submit PR** — Follow PR template

## Reporting Bugs

Use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.md) and include:

- Clear description
- Steps to reproduce
- Expected vs actual behavior
- Environment details
- Logs/stack traces
- Minimal reproduction (if possible)

## Requesting Features

Use the [feature request template](.github/ISSUE_TEMPLATE/feature_request.md) and include:

- Problem statement
- Proposed solution
- Alternatives considered
- Implementation ideas (optional)

## Development Phases

See **ROADMAP.md** for the 20-week implementation plan. Current priorities:

- **Phase 1 (Weeks 1-4)**: Authentication, MFA, basic API
- **Phase 2 (Weeks 5-8)**: Task management, transaction logging
- **Phase 3 (Weeks 9-12)**: Financial intelligence, OCR
- **Phase 4 (Weeks 13-16)**: Knowledge base, semantic search
- **Phase 5 (Weeks 17-20)**: Automation, production hardening

## Security

**Do not** commit:
- API keys or secrets
- `.env` files (use `.env.example`)
- Personal data
- Credentials

**Do**:
- Use environment variables
- Follow `docs/OPERATIONS.md` security guidelines
- Report vulnerabilities privately (email maintainer)

## Questions?

- Open a [Discussion](https://github.com/MerverliPy/nexus/discussions) (when enabled)
- Create an [Issue](https://github.com/MerverliPy/nexus/issues)
- Review existing issues for similar questions

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to Nexus! 🚀

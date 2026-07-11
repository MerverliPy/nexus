# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial project structure and foundation
- Complete technical specification (SPECIFICATION.md)
- 20-week implementation roadmap (ROADMAP.md)
- Security and operations guide (docs/OPERATIONS.md)
- Quick start guide (QUICKSTART.md)
- Database models for all domains:
  - User model with MFA/TOTP support
  - Task model with recurrence
  - Finance models (Account, Transaction)
  - Research models (Note, ResearchProject, NoteLink)
  - Automation model
  - AuditLog model
- FastAPI application scaffold
- Alembic migration environment (async-ready)
- Docker Compose infrastructure (PostgreSQL, Redis, MinIO, Prometheus, Grafana)
- CLI scaffold with Click
- Pytest fixtures and sample tests
- GitHub Actions CI workflow
- Contributing guidelines
- Issue and PR templates
- Budget forecasting with ML — sklearn per-category regression + 95% CI + CLI (`nexus finance forecast`) + API + 8 tests
- Categorization accuracy tracking — prediction log, per-category stats, accuracy endpoint + 10 tests
- Vendor normalization — VendorAlias model, fuzzy matching (difflib), merge/alias APIs + 17 tests
- Note versioning (git-backed) — auto-commit on save, history/restore endpoints, CLI + 10 tests

### Infrastructure
- Docker Compose setup with 6 services
- Health checks for all services
- Volume persistence
- Network isolation
- Prometheus metrics collection
- Grafana dashboards (configuration pending)

### Documentation
- README.md with project overview
- SPECIFICATION.md (968 lines)
- ROADMAP.md (676 lines)
- docs/OPERATIONS.md (1,192 lines)
- QUICKSTART.md (190 lines)
- SUMMARY.md with package overview
- CHECKLIST.md for pre-launch verification
- DELIVERY.md with comprehensive summary
- CONTRIBUTING.md with development guidelines

## [0.1.0] - 2026-07-09

### Added
- Initial release
- Project foundation complete
- Production-ready architecture
- 4,769 lines of code and documentation
- 31 files across all domains

### Notes
- This is a foundation release
- Authentication endpoints not yet implemented
- Frontend not included (planned for Phase 2)
- See ROADMAP.md for implementation schedule

---

## Release Checklist

Before each release:
- [ ] All tests passing
- [ ] Documentation updated
- [ ] Migration scripts tested
- [ ] CHANGELOG.md updated
- [ ] Version bumped in pyproject.toml
- [ ] Git tag created
- [ ] GitHub release published
- [ ] Docker images built (when applicable)

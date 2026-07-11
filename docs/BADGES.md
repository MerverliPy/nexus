# Nexus Repository Badges

This document contains badge configurations for README.md and other documentation.

## Current Badges

### Build & CI Status
```markdown
[![CI](https://github.com/calvin/nexus/actions/workflows/ci.yml/badge.svg)](https://github.com/calvin/nexus/actions/workflows/ci.yml)
[![Tests](https://github.com/calvin/nexus/actions/workflows/tests.yml/badge.svg)](https://github.com/calvin/nexus/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/calvin/nexus/branch/main/graph/badge.svg)](https://codecov.io/gh/calvin/nexus)
```

### Version & License
```markdown
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-0.1.0-green.svg)](https://github.com/calvin/nexus/releases)
```

### Code Quality
```markdown
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Type Checked: mypy](https://img.shields.io/badge/type_checked-mypy-blue.svg)](https://mypy-lang.org/)
```

### Documentation
```markdown
[![Documentation](https://img.shields.io/badge/docs-latest-brightgreen.svg)](https://github.com/calvin/nexus/tree/main/docs)
[![FAQ](https://img.shields.io/badge/FAQ-available-blue.svg)](https://github.com/calvin/nexus/blob/main/docs/FAQ.md)
[![Getting Started](https://img.shields.io/badge/guide-getting_started-orange.svg)](https://github.com/calvin/nexus/blob/main/GETTING_STARTED.md)
```

### Community & Support
```markdown
[![GitHub issues](https://img.shields.io/github/issues/calvin/nexus)](https://github.com/calvin/nexus/issues)
[![GitHub pull requests](https://img.shields.io/github/issues-pr/calvin/nexus)](https://github.com/calvin/nexus/pulls)
[![GitHub stars](https://img.shields.io/github/stars/calvin/nexus?style=social)](https://github.com/calvin/nexus)
[![GitHub forks](https://img.shields.io/github/forks/calvin/nexus?style=social)](https://github.com/calvin/nexus/network/members)
```

### Platform Support
```markdown
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg?logo=docker)](https://hub.docker.com/)
[![PostgreSQL](https://img.shields.io/badge/postgresql-16+-blue.svg?logo=postgresql)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/redis-7.2+-red.svg?logo=redis)](https://redis.io/)
[![FastAPI](https://img.shields.io/badge/fastapi-latest-teal.svg?logo=fastapi)](https://fastapi.tiangolo.com/)
```

---

## Suggested Badge Layout for README.md

Place at the top after the title:

```markdown
# Nexus Personal AI System

<p align="center">
  <img src="docs/assets/logo.png" alt="Nexus Logo" width="200"/>
</p>

<p align="center">
  <em>Your AI-powered personal command center for tasks, finance, and research</em>
</p>

<p align="center">
  <!-- Build Status -->
  <a href="https://github.com/calvin/nexus/actions/workflows/ci.yml">
    <img src="https://github.com/calvin/nexus/actions/workflows/ci.yml/badge.svg" alt="CI Status"/>
  </a>
  <!-- License -->
  <a href="https://opensource.org/licenses/MIT">
    <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"/>
  </a>
  <!-- Python Version -->
  <a href="https://www.python.org/downloads/">
    <img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+"/>
  </a>
  <!-- Version -->
  <a href="https://github.com/calvin/nexus/releases">
    <img src="https://img.shields.io/badge/version-0.1.0-green.svg" alt="Version 0.1.0"/>
  </a>
  <!-- Code Style -->
  <a href="https://github.com/psf/black">
    <img src="https://img.shields.io/badge/code%20style-black-000000.svg" alt="Code style: black"/>
  </a>
</p>

<p align="center">
  <a href="#-quick-start">Quick Start</a> •
  <a href="GETTING_STARTED.md">Getting Started Guide</a> •
  <a href="docs/FAQ.md">FAQ</a> •
  <a href="CONTRIBUTING.md">Contributing</a> •
  <a href="ROADMAP.md">Roadmap</a>
</p>

---
```

---

## Dynamic Badges (Configure via GitHub Actions)

### Code Coverage Badge

Add to `.github/workflows/coverage.yml`:
```yaml
- name: Upload coverage to Codecov
  uses: codecov/codecov-action@v4
  with:
    token: ${{ secrets.CODECOV_TOKEN }}
    files: ./coverage.xml
    fail_ci_if_error: true
```

Then add badge:
```markdown
[![codecov](https://codecov.io/gh/calvin/nexus/branch/main/graph/badge.svg)](https://codecov.io/gh/calvin/nexus)
```

### Docker Image Size

If you publish to Docker Hub:
```markdown
[![Docker Image Size](https://img.shields.io/docker/image-size/calvin/nexus/latest)](https://hub.docker.com/r/calvin/nexus)
[![Docker Pulls](https://img.shields.io/docker/pulls/calvin/nexus)](https://hub.docker.com/r/calvin/nexus)
```

### Security Scanning

Add Snyk or Dependabot:
```markdown
[![Known Vulnerabilities](https://snyk.io/test/github/calvin/nexus/badge.svg)](https://snyk.io/test/github/calvin/nexus)
[![Dependabot Status](https://api.dependabot.com/badges/status?host=github&repo=calvin/nexus)](https://dependabot.com)
```

---

## Custom Badges

Create custom badges at [shields.io](https://shields.io/):

### Roadmap Progress
```markdown
![Phase](https://img.shields.io/badge/Phase-1_of_10-blue)
![Progress](https://img.shields.io/badge/Progress-10%25-yellow)
```

### Model Support
```markdown
![OpenRouter](https://img.shields.io/badge/OpenRouter-200%2B_models-green)
![Ollama](https://img.shields.io/badge/Ollama-local_models-blue)
```

### Features
```markdown
![Tasks](https://img.shields.io/badge/Tasks-Smart_Scheduling-brightgreen)
![Finance](https://img.shields.io/badge/Finance-OCR%20%2B%20ML-orange)
![Research](https://img.shields.io/badge/Research-Semantic_Search-purple)
```

---

## Badge Best Practices

### DO:
- ✅ Keep badges at top of README
- ✅ Use official badge services (shields.io, GitHub Actions)
- ✅ Group related badges (build, quality, docs)
- ✅ Link badges to relevant pages
- ✅ Update badge URLs when repo name changes

### DON'T:
- ❌ Clutter with too many badges (max 10-12)
- ❌ Use broken/outdated badge services
- ❌ Add badges for trivial info
- ❌ Link badges to 404 pages
- ❌ Use low-quality custom badges

---

## Recommended Badge Set for Nexus

**Minimal (5 badges):**
1. CI Status
2. License
3. Python Version
4. Version
5. Code Style

**Standard (8 badges):**
1-5 from minimal, plus:
6. Documentation
7. Issues
8. Stars

**Full (12 badges):**
1-8 from standard, plus:
9. Test Coverage
10. Docker
11. PostgreSQL
12. FastAPI

---

## Updating Badges

When releasing new versions, update:

1. **Version badge:**
   ```markdown
   ![Version](https://img.shields.io/badge/version-0.2.0-green.svg)
   ```

2. **Roadmap progress:**
   ```markdown
   ![Phase](https://img.shields.io/badge/Phase-2_of_10-blue)
   ![Progress](https://img.shields.io/badge/Progress-20%25-yellow)
   ```

3. **Changelog link in release notes**

---

**For more badge customization, visit:**  
- [Shields.io](https://shields.io/)
- [Simple Icons](https://simpleicons.org/) (for logos)
- [Badgen](https://badgen.net/) (alternative generator)

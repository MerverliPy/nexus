# Security Policy

## 🔒 Reporting Security Vulnerabilities

**Please do NOT report security vulnerabilities through public GitHub issues.**

If you discover a security vulnerability in Nexus, please report it privately to protect users:

### Preferred Method: Private Security Advisory

1. Go to the [Security Advisories](https://github.com/calvin/nexus/security/advisories) page
2. Click "Report a vulnerability"
3. Fill out the advisory form with:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if you have one)

### Alternative Method: Direct Email

Send an email to **calvinbrady8@gmail.com** with:

- **Subject:** `[SECURITY] Nexus - <Brief Description>`
- **Body:** Detailed description, reproduction steps, and impact assessment
- **PGP Encryption:** (Optional, but appreciated for sensitive reports)

---

## 🛡️ Security Response Process

1. **Acknowledgment** - You'll receive confirmation within 48 hours
2. **Investigation** - We'll assess the issue and severity
3. **Fix Development** - A patch will be developed if confirmed
4. **Coordinated Disclosure** - We'll work with you on a disclosure timeline
5. **Public Release** - Security advisory published with credit to reporter

---

## ⚡ Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1   | :x:                |

> **Note:** Nexus is in early development (pre-1.0). Security patches are released as soon as possible, typically within 7-14 days of confirmed vulnerability.

---

## 🔐 Security Best Practices

When self-hosting Nexus, follow these security recommendations:

### Authentication & Access Control

- ✅ **Enable MFA** - Configure TOTP two-factor authentication (see `docs/OPERATIONS.md` section 1.2)
- ✅ **Strong Passwords** - Use 16+ character passwords with mixed case, numbers, and symbols
- ✅ **JWT Secret Rotation** - Rotate `NEXUS_SECRET_KEY` periodically (every 90 days recommended)
- ✅ **Limit API Access** - Use network firewalls to restrict API access to trusted IPs

### Data Protection

- ✅ **Encrypted Storage** - Enable field-level encryption for sensitive data (`NEXUS_ENABLE_ENCRYPTION=true`)
- ✅ **Secure Backups** - Encrypt database backups at rest
- ✅ **Environment Variables** - Never commit `.env` files to version control
- ✅ **MinIO Access Keys** - Rotate MinIO credentials regularly

### Infrastructure

- ✅ **TLS/HTTPS** - Use reverse proxy (nginx/Caddy) with Let's Encrypt certificates
- ✅ **Container Security** - Run Docker containers as non-root users
- ✅ **Regular Updates** - Keep dependencies up to date (`pip list --outdated`)
- ✅ **Network Isolation** - Use Docker networks to isolate services

### Monitoring & Logging

- ✅ **Audit Logs** - Enable comprehensive audit logging (`NEXUS_ENABLE_AUDIT_LOGS=true`)
- ✅ **Failed Login Alerts** - Monitor for suspicious authentication attempts
- ✅ **Resource Monitoring** - Track CPU/memory/disk usage for anomalies
- ✅ **Security Scanning** - Run `safety check` on Python dependencies regularly

---

## 🚨 Known Security Considerations

### Current Limitations (as of v0.1.0)

1. **Rate Limiting** - API rate limiting is basic; implement reverse proxy rate limiting for production
2. **CSRF Protection** - Web UI lacks CSRF tokens (Phase 3 roadmap item)
3. **Input Sanitization** - LLM prompt injection mitigations are in progress
4. **Audit Log Retention** - No automated log rotation yet (manual cleanup required)

These limitations are tracked in the public roadmap and will be addressed in future releases.

---

## 📚 Security Resources

- **OWASP Top 10** - [https://owasp.org/www-project-top-ten/](https://owasp.org/www-project-top-ten/)
- **FastAPI Security** - [https://fastapi.tiangolo.com/tutorial/security/](https://fastapi.tiangolo.com/tutorial/security/)
- **Docker Security** - [https://docs.docker.com/engine/security/](https://docs.docker.com/engine/security/)
- **PostgreSQL Security** - [https://www.postgresql.org/docs/current/security.html](https://www.postgresql.org/docs/current/security.html)

---

## 🏆 Security Hall of Fame

We appreciate responsible disclosure and will credit security researchers who report valid vulnerabilities:

*(No reports yet - be the first!)*

---

**Last Updated:** 2026-07-10  
**Security Contact:** calvinbrady8@gmail.com

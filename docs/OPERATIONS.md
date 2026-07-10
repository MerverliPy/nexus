# Nexus Operations & Security Hardening Guide

**Version:** 1.0.0  
**Last Updated:** 2026-07-09  
**Audience:** System administrators, DevOps, security engineers

---

## Table of Contents

1. [Security Hardening](#security-hardening)
2. [Multi-Factor Authentication Setup](#multi-factor-authentication-setup)
3. [Database Encryption](#database-encryption)
4. [WSL2 systemd Services](#wsl2-systemd-services)
5. [Backup & Disaster Recovery](#backup--disaster-recovery)
6. [Monitoring & Alerting](#monitoring--alerting)
7. [Cost Tracking & Budget Alerts](#cost-tracking--budget-alerts)
8. [Incident Response Playbook](#incident-response-playbook)
9. [Maintenance Procedures](#maintenance-procedures)

---

## Security Hardening

### Initial Security Checklist

Before going to production, complete these steps:

- [ ] **Change all default passwords**
  - PostgreSQL: `ALTER USER nexus_user PASSWORD 'strong-random-password';`
  - Redis: Set `requirepass` in `/etc/redis/redis.conf`
  - MinIO: Change default `minioadmin:minioadmin` credentials

- [ ] **Generate secure secrets**
  ```bash
  # JWT secret key (32 bytes hex)
  openssl rand -hex 32
  
  # Database encryption key (32 bytes base64)
  openssl rand -base64 32
  
  # Session secret (32 bytes hex)
  openssl rand -hex 32
  ```

- [ ] **Set environment variables**
  ```bash
  # Add to ~/.bashrc or ~/.zshrc
  export NEXUS_DB_PASSWORD="..."
  export NEXUS_SECRET_KEY="..."
  export NEXUS_ENCRYPTION_KEY="..."
  export OPENROUTER_API_KEY="..."
  export TELEGRAM_BOT_TOKEN="..."
  ```

- [ ] **Firewall configuration**
  ```bash
  # WSL2: Block external access to internal services
  sudo ufw enable
  sudo ufw default deny incoming
  sudo ufw default allow outgoing
  sudo ufw allow from 127.0.0.1 to any port 5432  # PostgreSQL
  sudo ufw allow from 127.0.0.1 to any port 6379  # Redis
  sudo ufw allow from 127.0.0.1 to any port 9000  # MinIO
  ```

- [ ] **TLS certificate setup**
  ```bash
  # Caddy auto-HTTPS (requires domain name pointing to your IP)
  # If local-only, generate self-signed cert:
  openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
  ```

---

## Multi-Factor Authentication Setup

### Implementing TOTP (Time-based One-Time Password)

#### Backend Implementation

**Install dependencies:**
```bash
pip install pyotp qrcode[pil]
```

**User model update:**
```python
# src/nexus/models/user.py
from sqlalchemy import Column, String, Boolean
from sqlalchemy_utils import EncryptedType
from sqlalchemy_utils.types.encrypted.encrypted_type import AesEngine
import os

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    
    # Encrypted TOTP secret (only set if MFA enabled)
    totp_secret = Column(
        EncryptedType(String(32), os.environ['NEXUS_ENCRYPTION_KEY'], AesEngine, 'pkcs5'),
        nullable=True
    )
    mfa_enabled = Column(Boolean, default=False)
    
    # Encrypted backup codes (JSON array of strings)
    backup_codes = Column(
        EncryptedType(Text, os.environ['NEXUS_ENCRYPTION_KEY'], AesEngine, 'pkcs5'),
        nullable=True
    )
```

**MFA enrollment endpoint:**
```python
# src/nexus/api/auth.py
import pyotp
import qrcode
import io
import base64

@router.post("/auth/mfa/enroll")
async def enroll_mfa(current_user: User = Depends(get_current_user)):
    """Generate TOTP secret and QR code for MFA enrollment."""
    
    # Generate secret (base32 encoded)
    secret = pyotp.random_base32()
    
    # Generate provisioning URI
    totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=current_user.email,
        issuer_name="Nexus"
    )
    
    # Generate QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(totp_uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64 for embedding in JSON response
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    qr_base64 = base64.b64encode(buf.getvalue()).decode()
    
    return {
        "secret": secret,
        "qr_code": f"data:image/png;base64,{qr_base64}",
        "manual_entry": secret  # For users who can't scan QR
    }

@router.post("/auth/mfa/verify")
async def verify_mfa(
    totp_code: str,
    secret: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Verify TOTP code and enable MFA for user."""
    
    totp = pyotp.TOTP(secret)
    
    if not totp.verify(totp_code, valid_window=1):  # Allow 1 interval tolerance (±30s)
        raise HTTPException(status_code=400, detail="Invalid TOTP code")
    
    # Generate 10 backup codes
    backup_codes = [pyotp.random_base32()[:8] for _ in range(10)]
    
    # Enable MFA and store encrypted secret + backup codes
    current_user.totp_secret = secret
    current_user.mfa_enabled = True
    current_user.backup_codes = json.dumps(backup_codes)
    
    await db.commit()
    
    return {
        "success": True,
        "backup_codes": backup_codes,
        "message": "MFA enabled. Save backup codes in a secure location."
    }
```

**Login with MFA:**
```python
@router.post("/auth/login")
async def login(
    credentials: LoginSchema,
    db: AsyncSession = Depends(get_db)
):
    user = await authenticate_user(db, credentials.email, credentials.password)
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # If MFA enabled, require TOTP code
    if user.mfa_enabled:
        if not credentials.totp_code:
            return {
                "mfa_required": True,
                "message": "MFA enabled. Please provide TOTP code."
            }
        
        totp = pyotp.TOTP(user.totp_secret)
        if not totp.verify(credentials.totp_code, valid_window=1):
            # Check backup codes
            backup_codes = json.loads(user.backup_codes)
            if credentials.totp_code not in backup_codes:
                raise HTTPException(status_code=401, detail="Invalid TOTP code")
            
            # Mark backup code as used (remove from list)
            backup_codes.remove(credentials.totp_code)
            user.backup_codes = json.dumps(backup_codes)
            await db.commit()
    
    # Generate JWT tokens
    access_token = create_access_token(data={"sub": user.email})
    refresh_token = create_refresh_token(data={"sub": user.email})
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }
```

#### CLI Implementation

```python
# src/nexus/cli/auth.py
import click
from rich.console import Console
from rich.prompt import Prompt

console = Console()

@click.command()
def enable_mfa():
    """Enable multi-factor authentication."""
    
    # Call enrollment endpoint
    response = api_client.post("/auth/mfa/enroll")
    data = response.json()
    
    # Display QR code in terminal (requires terminal with image support)
    # For text-only terminals, display secret for manual entry
    console.print("\n[bold]Scan this QR code with Google Authenticator:[/bold]")
    console.print(f"\nManual entry code: [cyan]{data['secret']}[/cyan]")
    
    # Prompt for TOTP code to verify
    totp_code = Prompt.ask("\nEnter the 6-digit code from your authenticator app")
    
    # Verify and enable
    verify_response = api_client.post("/auth/mfa/verify", json={
        "totp_code": totp_code,
        "secret": data['secret']
    })
    
    result = verify_response.json()
    
    if result['success']:
        console.print("\n✓ [green]MFA enabled successfully![/green]")
        console.print("\n[bold yellow]BACKUP CODES (save these securely):[/bold yellow]")
        for code in result['backup_codes']:
            console.print(f"  • {code}")
    else:
        console.print(f"\n✗ [red]Error: {result['message']}[/red]")
```

---

## Database Encryption

### Field-Level Encryption with SQLAlchemy-Utils

**Setup:**
```bash
pip install sqlalchemy-utils cryptography
```

**Generate encryption key:**
```bash
# Generate 32-byte key (must be stored securely, NOT in repo)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Export as environment variable
export NEXUS_ENCRYPTION_KEY="<generated-key>"
```

**Encrypted model fields:**
```python
# src/nexus/models/account.py
from sqlalchemy import Column, Integer, String, DECIMAL
from sqlalchemy_utils import EncryptedType
from sqlalchemy_utils.types.encrypted.encrypted_type import AesEngine
import os

class Account(Base):
    __tablename__ = "accounts"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String(255), nullable=False)
    account_type = Column(String(50))
    
    # Encrypted field: Plaid access token
    encrypted_credentials = Column(
        EncryptedType(
            String,  # Original type
            os.environ.get('NEXUS_ENCRYPTION_KEY'),  # Encryption key
            AesEngine,  # Encryption algorithm (AES-256)
            'pkcs5'  # Padding scheme
        ),
        nullable=True
    )
    
    balance = Column(DECIMAL(12, 2), default=0)
```

**Usage (transparent encryption/decryption):**
```python
# Create account with encrypted credentials
account = Account(
    user_id=1,
    name="Chase Checking",
    encrypted_credentials="plaid_access_token_xxx"  # Automatically encrypted before save
)
db.add(account)
await db.commit()

# Retrieve account (automatically decrypted)
account = await db.get(Account, 1)
print(account.encrypted_credentials)  # Prints decrypted value
```

**Key rotation procedure:**
```python
# scripts/rotate_encryption_key.py
import os
from sqlalchemy import select
from nexus.models import Account, User
from nexus.database import SessionLocal

OLD_KEY = os.environ['NEXUS_OLD_ENCRYPTION_KEY']
NEW_KEY = os.environ['NEXUS_ENCRYPTION_KEY']

async def rotate_keys():
    """Re-encrypt all sensitive fields with new key."""
    
    async with SessionLocal() as db:
        # Temporarily set old key to decrypt
        os.environ['NEXUS_ENCRYPTION_KEY'] = OLD_KEY
        
        # Load all accounts
        accounts = await db.execute(select(Account))
        accounts = accounts.scalars().all()
        
        # Decrypt with old key
        decrypted_data = []
        for account in accounts:
            decrypted_data.append({
                'id': account.id,
                'credentials': account.encrypted_credentials
            })
        
        # Switch to new key
        os.environ['NEXUS_ENCRYPTION_KEY'] = NEW_KEY
        
        # Re-encrypt with new key
        for data in decrypted_data:
            account = await db.get(Account, data['id'])
            account.encrypted_credentials = data['credentials']
        
        await db.commit()
        print(f"✓ Rotated encryption key for {len(accounts)} accounts")

# Run quarterly or when key is compromised
```

### Database-Level Encryption (PostgreSQL TDE)

**Option 1: LUKS volume encryption (Linux)**
```bash
# Create encrypted volume
sudo cryptsetup luksFormat /dev/sdb1
sudo cryptsetup luksOpen /dev/sdb1 encrypted_db

# Format and mount
sudo mkfs.ext4 /dev/mapper/encrypted_db
sudo mount /dev/mapper/encrypted_db /var/lib/postgresql

# Auto-mount on boot (requires keyfile or passphrase prompt)
echo "encrypted_db /dev/sdb1 /root/keyfile luks" | sudo tee -a /etc/crypttab
```

**Option 2: PostgreSQL pgcrypto extension**
```sql
-- Enable pgcrypto extension
CREATE EXTENSION pgcrypto;

-- Encrypt entire column (not recommended for performance)
CREATE TABLE sensitive_data (
    id SERIAL PRIMARY KEY,
    encrypted_field BYTEA
);

INSERT INTO sensitive_data (encrypted_field) 
VALUES (pgp_sym_encrypt('secret data', 'encryption_key'));

SELECT pgp_sym_decrypt(encrypted_field, 'encryption_key') 
FROM sensitive_data;
```

---

## WSL2 systemd Services

### Enable systemd in WSL2

**Edit `/etc/wsl.conf`:**
```ini
[boot]
systemd=true
```

**Restart WSL2:**
```powershell
# From PowerShell (Windows host)
wsl --shutdown
wsl
```

### Create Nexus Backend Service

**`/etc/systemd/system/nexus-backend.service`:**
```ini
[Unit]
Description=Nexus FastAPI Backend
After=network.target postgresql.service redis.service
Wants=postgresql.service redis.service

[Service]
Type=simple
User=calvin
Group=calvin
WorkingDirectory=/home/calvin/nexus

# Environment variables
Environment="PATH=/home/calvin/nexus/venv/bin:/usr/local/bin:/usr/bin"
Environment="NEXUS_ENV=production"
EnvironmentFile=/home/calvin/nexus/.env

# Start command
ExecStart=/home/calvin/nexus/venv/bin/uvicorn \
    nexus.api.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 2 \
    --log-config /home/calvin/nexus/config/logging.ini

# Restart policy
Restart=always
RestartSec=10
StartLimitBurst=5
StartLimitIntervalSec=300

# Resource limits
LimitNOFILE=65536
MemoryLimit=1G

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=nexus-backend

[Install]
WantedBy=multi-user.target
```

### Create Celery Worker Service

**`/etc/systemd/system/nexus-worker.service`:**
```ini
[Unit]
Description=Nexus Celery Worker
After=network.target redis.service
Wants=redis.service

[Service]
Type=simple
User=calvin
Group=calvin
WorkingDirectory=/home/calvin/nexus

Environment="PATH=/home/calvin/nexus/venv/bin:/usr/local/bin:/usr/bin"
EnvironmentFile=/home/calvin/nexus/.env

ExecStart=/home/calvin/nexus/venv/bin/celery \
    -A nexus.workers.app \
    worker \
    --loglevel=info \
    --concurrency=4 \
    --max-tasks-per-child=1000

Restart=always
RestartSec=10

StandardOutput=journal
StandardError=journal
SyslogIdentifier=nexus-worker

[Install]
WantedBy=multi-user.target
```

### Create Celery Beat Service (Scheduler)

**`/etc/systemd/system/nexus-beat.service`:**
```ini
[Unit]
Description=Nexus Celery Beat Scheduler
After=network.target redis.service
Wants=redis.service

[Service]
Type=simple
User=calvin
Group=calvin
WorkingDirectory=/home/calvin/nexus

Environment="PATH=/home/calvin/nexus/venv/bin:/usr/local/bin:/usr/bin"
EnvironmentFile=/home/calvin/nexus/.env

ExecStart=/home/calvin/nexus/venv/bin/celery \
    -A nexus.workers.app \
    beat \
    --loglevel=info \
    --scheduler django_celery_beat.schedulers:DatabaseScheduler

Restart=always
RestartSec=10

StandardOutput=journal
StandardError=journal
SyslogIdentifier=nexus-beat

[Install]
WantedBy=multi-user.target
```

### Service Management Commands

```bash
# Enable services (start on boot)
sudo systemctl enable nexus-backend nexus-worker nexus-beat

# Start services
sudo systemctl start nexus-backend nexus-worker nexus-beat

# Check status
sudo systemctl status nexus-backend

# View logs
sudo journalctl -u nexus-backend -f  # Follow logs
sudo journalctl -u nexus-backend --since "1 hour ago"

# Restart after code changes
sudo systemctl restart nexus-backend nexus-worker

# Stop services
sudo systemctl stop nexus-backend nexus-worker nexus-beat
```

### Auto-restart on Windows Boot

**Create startup script on Windows:**

`C:\Users\<username>\startup-nexus.bat`:
```batch
@echo off
wsl -d Ubuntu -u calvin -- systemctl --user start nexus-backend nexus-worker nexus-beat
```

**Add to Windows Startup folder:**
- Press `Win + R`, type `shell:startup`, press Enter
- Copy `startup-nexus.bat` to this folder

---

## Backup & Disaster Recovery

### Automated Daily Backups

**`scripts/backup.sh`:**
```bash
#!/bin/bash
set -euo pipefail

# Configuration
BACKUP_DIR="/home/calvin/nexus/backups"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=90

# PostgreSQL credentials
export PGPASSWORD="${NEXUS_DB_PASSWORD}"
DB_USER="nexus_user"
DB_NAME="nexus_db"

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"

# 1. PostgreSQL backup
echo "Starting PostgreSQL backup..."
pg_dump -U "$DB_USER" -h localhost "$DB_NAME" | gzip > "$BACKUP_DIR/db_$DATE.sql.gz"

# 2. MinIO backup (receipts, documents)
echo "Starting MinIO backup..."
mc mirror --overwrite local/nexus-receipts "$BACKUP_DIR/minio_$DATE/"

# 3. Configuration files backup
echo "Backing up configuration..."
tar -czf "$BACKUP_DIR/config_$DATE.tar.gz" \
    ~/.nexus/config.toml \
    /home/calvin/nexus/.env \
    /etc/systemd/system/nexus-*.service

# 4. Encrypt backups
echo "Encrypting backups..."
gpg --batch --yes --encrypt --recipient backup@nexus.local \
    "$BACKUP_DIR/db_$DATE.sql.gz"
gpg --batch --yes --encrypt --recipient backup@nexus.local \
    "$BACKUP_DIR/config_$DATE.tar.gz"

# 5. Upload to cloud (Backblaze B2)
echo "Uploading to cloud storage..."
b2 upload-file nexus-backup "$BACKUP_DIR/db_$DATE.sql.gz.gpg" \
    "backups/db_$DATE.sql.gz.gpg"
b2 upload-file nexus-backup "$BACKUP_DIR/config_$DATE.tar.gz.gpg" \
    "backups/config_$DATE.tar.gz.gpg"

# 6. Cleanup old backups (retain 90 days)
echo "Cleaning up old backups..."
find "$BACKUP_DIR" -name "db_*.sql.gz*" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "config_*.tar.gz*" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -type d -name "minio_*" -mtime +$RETENTION_DAYS -exec rm -rf {} +

# 7. Verify backup integrity
echo "Verifying backup integrity..."
gunzip -t "$BACKUP_DIR/db_$DATE.sql.gz"

echo "✓ Backup completed: $DATE"

# Send Telegram notification
curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -d "chat_id=${TELEGRAM_CHAT_ID}" \
    -d "text=✓ Nexus backup completed: $DATE"
```

**Make executable and schedule:**
```bash
chmod +x scripts/backup.sh

# Add to crontab (daily at 3am)
crontab -e
# Add line:
0 3 * * * /home/calvin/nexus/scripts/backup.sh >> /home/calvin/nexus/logs/backup.log 2>&1
```

### Backup Restoration Procedure

**`scripts/restore.sh`:**
```bash
#!/bin/bash
set -euo pipefail

# Usage: ./restore.sh <backup_date>
# Example: ./restore.sh 20260709_030000

BACKUP_DATE=$1
BACKUP_DIR="/home/calvin/nexus/backups"

# 1. Stop services
echo "Stopping services..."
sudo systemctl stop nexus-backend nexus-worker nexus-beat

# 2. Decrypt backup
echo "Decrypting backup..."
gpg --decrypt "$BACKUP_DIR/db_${BACKUP_DATE}.sql.gz.gpg" > "$BACKUP_DIR/db_${BACKUP_DATE}.sql.gz"

# 3. Drop and recreate database
echo "Recreating database..."
dropdb -U nexus_user nexus_db
createdb -U nexus_user nexus_db

# 4. Restore database
echo "Restoring database..."
gunzip -c "$BACKUP_DIR/db_${BACKUP_DATE}.sql.gz" | psql -U nexus_user nexus_db

# 5. Restore MinIO data
echo "Restoring MinIO data..."
mc mirror --overwrite "$BACKUP_DIR/minio_${BACKUP_DATE}/" local/nexus-receipts

# 6. Start services
echo "Starting services..."
sudo systemctl start nexus-backend nexus-worker nexus-beat

echo "✓ Restore completed from backup: $BACKUP_DATE"
```

### Weekly Backup Restoration Test

**`scripts/test-restore.sh`:**
```bash
#!/bin/bash
set -euo pipefail

BACKUP_DIR="/home/calvin/nexus/backups"
LATEST_BACKUP=$(ls -t $BACKUP_DIR/db_*.sql.gz | head -1)

# Use staging database for test
export PGPASSWORD="${NEXUS_DB_PASSWORD}"
DB_USER="nexus_user"
STAGING_DB="nexus_staging"

echo "Testing restore from: $LATEST_BACKUP"

# Create staging database
dropdb -U "$DB_USER" "$STAGING_DB" 2>/dev/null || true
createdb -U "$DB_USER" "$STAGING_DB"

# Restore to staging
gunzip -c "$LATEST_BACKUP" | psql -U "$DB_USER" "$STAGING_DB"

# Run health checks
echo "Running health checks..."
psql -U "$DB_USER" "$STAGING_DB" -c "SELECT COUNT(*) FROM users;" > /dev/null
psql -U "$DB_USER" "$STAGING_DB" -c "SELECT COUNT(*) FROM transactions;" > /dev/null

# Cleanup
dropdb -U "$DB_USER" "$STAGING_DB"

echo "✓ Backup restoration test passed"

# Send Telegram notification
curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -d "chat_id=${TELEGRAM_CHAT_ID}" \
    -d "text=✓ Weekly backup restoration test passed"
```

**Schedule weekly test:**
```bash
# Add to crontab (Sundays at 2am)
0 2 * * 0 /home/calvin/nexus/scripts/test-restore.sh >> /home/calvin/nexus/logs/restore-test.log 2>&1
```

---

## Monitoring & Alerting

### Prometheus Metrics

**Install prometheus-client:**
```bash
pip install prometheus-client
```

**FastAPI metrics middleware:**
```python
# src/nexus/api/middleware/metrics.py
from prometheus_client import Counter, Histogram, Gauge
from starlette.middleware.base import BaseHTTPMiddleware
import time

# Define metrics
request_count = Counter(
    'nexus_http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

request_duration = Histogram(
    'nexus_http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

active_requests = Gauge(
    'nexus_active_requests',
    'Number of active HTTP requests'
)

class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        active_requests.inc()
        
        start_time = time.time()
        response = await call_next(request)
        duration = time.time() - start_time
        
        # Record metrics
        request_count.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).inc()
        
        request_duration.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(duration)
        
        active_requests.dec()
        
        return response
```

**Metrics endpoint:**
```python
# src/nexus/api/main.py
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

### Grafana Dashboards

**Install Grafana:**
```bash
# Docker Compose
services:
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3001:3000"
    volumes:
      - grafana-data:/var/lib/grafana
      - ./config/grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./config/grafana/datasources:/etc/grafana/provisioning/datasources
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_USERS_ALLOW_SIGN_UP=false
```

**Dashboard: System Health**

JSON config at `config/grafana/dashboards/system-health.json`:
```json
{
  "dashboard": {
    "title": "Nexus System Health",
    "panels": [
      {
        "title": "Request Rate",
        "targets": [{
          "expr": "rate(nexus_http_requests_total[5m])"
        }],
        "type": "graph"
      },
      {
        "title": "Request Duration (p95)",
        "targets": [{
          "expr": "histogram_quantile(0.95, nexus_http_request_duration_seconds_bucket)"
        }],
        "type": "graph"
      },
      {
        "title": "Error Rate",
        "targets": [{
          "expr": "rate(nexus_http_requests_total{status=~\"5..\"}[5m])"
        }],
        "type": "graph"
      }
    ]
  }
}
```

### Alerting Rules (Alertmanager)

**`config/alertmanager/alerts.yml`:**
```yaml
groups:
  - name: nexus_alerts
    interval: 30s
    rules:
      # Service down
      - alert: NexusBackendDown
        expr: up{job="nexus-backend"} == 0
        for: 2m
        annotations:
          summary: "Nexus backend is down"
          description: "Backend service has been down for more than 2 minutes"
        labels:
          severity: critical
      
      # High error rate
      - alert: HighErrorRate
        expr: rate(nexus_http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value }} (threshold: 0.05)"
        labels:
          severity: warning
      
      # Disk usage
      - alert: DiskSpaceHigh
        expr: (node_filesystem_avail_bytes / node_filesystem_size_bytes) < 0.1
        for: 10m
        annotations:
          summary: "Disk space critically low"
          description: "Only {{ $value | humanizePercentage }} disk space available"
        labels:
          severity: critical
      
      # LLM API cost
      - alert: HighLLMCost
        expr: sum(increase(nexus_llm_cost_usd[1d])) > 5
        annotations:
          summary: "Daily LLM API cost exceeded threshold"
          description: "Cost today: ${{ $value }}"
        labels:
          severity: warning
```

**Telegram notification configuration:**

`config/alertmanager/alertmanager.yml`:
```yaml
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h
  receiver: 'telegram'

receivers:
  - name: 'telegram'
    webhook_configs:
      - url: 'http://localhost:9087/alert/-CHAT_ID'
        send_resolved: true

# Use prometheus-alertmanager-telegram-bot
# docker run -d -p 9087:9087 \
#   -e TELEGRAM_TOKEN="<bot_token>" \
#   metalmatze/alertmanager-bot:0.4.3
```

---

## Cost Tracking & Budget Alerts

### LLM API Cost Tracking

**Middleware to track token usage:**
```python
# src/nexus/services/llm.py
from sqlalchemy import Column, Integer, Float, DateTime, String
from nexus.models.base import Base
from datetime import datetime

class LLMUsage(Base):
    __tablename__ = "llm_usage"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    model = Column(String(100))
    prompt_tokens = Column(Integer)
    completion_tokens = Column(Integer)
    estimated_cost_usd = Column(Float)
    endpoint = Column(String(255))  # Which feature used the API
    created_at = Column(DateTime, default=datetime.utcnow)

# Token cost per model (update periodically)
MODEL_COSTS = {
    "claude-3-5-sonnet": {"prompt": 0.003, "completion": 0.015},  # per 1K tokens
    "gpt-4-turbo": {"prompt": 0.01, "completion": 0.03},
    "gpt-3.5-turbo": {"prompt": 0.0005, "completion": 0.0015},
}

async def call_llm_with_tracking(model, prompt, user_id, endpoint):
    """Call LLM API and track usage."""
    
    response = await llm_client.complete(model=model, prompt=prompt)
    
    # Calculate cost
    prompt_cost = (response.usage.prompt_tokens / 1000) * MODEL_COSTS[model]["prompt"]
    completion_cost = (response.usage.completion_tokens / 1000) * MODEL_COSTS[model]["completion"]
    total_cost = prompt_cost + completion_cost
    
    # Log usage
    usage = LLMUsage(
        user_id=user_id,
        model=model,
        prompt_tokens=response.usage.prompt_tokens,
        completion_tokens=response.usage.completion_tokens,
        estimated_cost_usd=total_cost,
        endpoint=endpoint
    )
    db.add(usage)
    await db.commit()
    
    return response
```

**Daily cost summary (Celery beat task):**
```python
# src/nexus/workers/tasks.py
from celery import shared_task
from datetime import datetime, timedelta
from sqlalchemy import select, func

@shared_task
def daily_cost_summary():
    """Send daily LLM cost summary via Telegram."""
    
    today = datetime.utcnow().date()
    yesterday = today - timedelta(days=1)
    
    # Query total cost for yesterday
    query = select(
        func.sum(LLMUsage.estimated_cost_usd).label("total_cost"),
        func.sum(LLMUsage.prompt_tokens + LLMUsage.completion_tokens).label("total_tokens"),
        LLMUsage.endpoint
    ).where(
        LLMUsage.created_at >= yesterday,
        LLMUsage.created_at < today
    ).group_by(LLMUsage.endpoint)
    
    results = db.execute(query).all()
    
    # Format message
    message = f"📊 *LLM Usage Summary - {yesterday}*\n\n"
    total_cost = 0
    
    for cost, tokens, endpoint in results:
        message += f"• {endpoint}: ${cost:.2f} ({tokens:,} tokens)\n"
        total_cost += cost
    
    message += f"\n*Total: ${total_cost:.2f}*"
    
    # Send Telegram notification
    send_telegram(message)
    
    # Alert if exceeds daily threshold
    if total_cost > 5:
        send_telegram(f"⚠️ Daily LLM cost exceeded threshold: ${total_cost:.2f}")
```

**Monthly budget tracking:**
```python
@shared_task
def check_monthly_budget():
    """Check if monthly LLM budget is exceeded."""
    
    MONTHLY_BUDGET = 50.0  # $50/month
    
    # Get month-to-date cost
    first_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0)
    
    query = select(func.sum(LLMUsage.estimated_cost_usd)).where(
        LLMUsage.created_at >= first_of_month
    )
    
    mtd_cost = db.scalar(query) or 0
    
    percent_used = (mtd_cost / MONTHLY_BUDGET) * 100
    
    # Alert at 80% and 100%
    if percent_used >= 100:
        send_telegram(f"🚨 Monthly LLM budget EXCEEDED: ${mtd_cost:.2f} / ${MONTHLY_BUDGET}")
    elif percent_used >= 80:
        send_telegram(f"⚠️ Monthly LLM budget at {percent_used:.0f}%: ${mtd_cost:.2f} / ${MONTHLY_BUDGET}")
```

---

## Incident Response Playbook

### Service Down

**Symptoms:** Uptime monitoring alert, users can't access system

**Response:**
1. Check service status: `sudo systemctl status nexus-backend`
2. Check logs: `sudo journalctl -u nexus-backend --since "10 minutes ago"`
3. Common fixes:
   - **Out of memory:** Restart service, increase MemoryLimit in systemd unit
   - **Port conflict:** `sudo lsof -i :8000` (kill conflicting process)
   - **Database connection:** Check PostgreSQL status: `sudo systemctl status postgresql`
4. Restart services: `sudo systemctl restart nexus-backend nexus-worker`
5. Verify recovery: `curl http://localhost:8000/health`

### Database Corruption

**Symptoms:** PostgreSQL errors, data inconsistencies

**Response:**
1. Immediate: Stop all writes (disable backend service)
2. Check integrity: `psql -U nexus_user nexus_db -c "SELECT * FROM pg_stat_database_conflicts;"`
3. If minor corruption: `REINDEX DATABASE nexus_db;`
4. If major corruption: Restore from last backup (see Backup Restoration Procedure)
5. Post-recovery: Investigate root cause (disk full? hardware failure?)

### Runaway Automation (Cost Spike)

**Symptoms:** LLM cost alert, high API request rate

**Response:**
1. Identify culprit: `SELECT automation_id, COUNT(*) FROM automation_runs WHERE created_at > NOW() - INTERVAL '1 hour' GROUP BY automation_id ORDER BY COUNT(*) DESC;`
2. Disable automation: `nexus auto disable <id>`
3. Review automation config: `nexus auto show <id>`
4. Fix bug in automation logic
5. Re-enable with rate limit: `nexus auto enable <id> --rate-limit 10/hour`

### Security Breach (Unauthorized Access)

**Symptoms:** Audit log shows unknown IP, unusual activity

**Response:**
1. **Immediate:** Revoke all active sessions: `DELETE FROM refresh_tokens;`
2. Force password reset for affected user
3. Review audit logs: `SELECT * FROM audit_logs WHERE created_at > NOW() - INTERVAL '24 hours' ORDER BY created_at DESC;`
4. Check for data exfiltration: Large file downloads, bulk transaction exports
5. Rotate API keys and encryption keys
6. Enable MFA if not already enabled
7. Report incident, conduct post-mortem

---

## Maintenance Procedures

### Quarterly Tasks

- [ ] **Rotate encryption keys** (run `scripts/rotate_encryption_key.py`)
- [ ] **Update dependencies** (`pip-audit`, `pip list --outdated`)
- [ ] **Review audit logs** (check for anomalies)
- [ ] **Prune old data** (delete transactions/notes older than retention period)
- [ ] **Vacuum PostgreSQL** (`VACUUM ANALYZE;`)
- [ ] **Check backup restoration** (manual test beyond weekly automation)

### Dependency Updates

```bash
# Check for security vulnerabilities
pip-audit

# Update dependencies
pip list --outdated
pip install --upgrade <package>

# Update requirements.txt
pip freeze > requirements.txt

# Test after updates
pytest
```

### Database Maintenance

```sql
-- Vacuum and analyze (reclaim space, update statistics)
VACUUM ANALYZE;

-- Reindex (rebuild indexes for performance)
REINDEX DATABASE nexus_db;

-- Check database size
SELECT pg_size_pretty(pg_database_size('nexus_db'));

-- Check table sizes
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

---

**End of Operations Guide**

*This guide should be reviewed and updated quarterly. Report any issues or gaps to the development team.*

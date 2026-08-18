# Sweetsnipe Hosted - Complete Guide

## What Is This?

Sweetsnipe Hosted is a **web-based, multi-tenant NFT minting service** built on top of the Sweetsnipe bot engine. Users access a beautiful dashboard through their browser, upload burner wallet keys (encrypted at rest), pay $1 per wallet, and launch mint jobs. You (the host) manage the infrastructure and earn revenue.

## Architecture

```
User Browser (Black/White Glossy UI)
    ↓ HTTPS
FastAPI Backend (Port 8000)
    ↓
SQLite Database (Users, Jobs, Workers, Payments)
    ↓
Job Queue (Asyncio-based)
    ↓
Sweetsnipe Engine (RPC, Mint, Transfer, Sweep)
```

## Key Security Features

1. **Encrypted Key Storage**: Private keys encrypted with Fernet (AES-128) before storing in database. Only decrypted in memory during job execution.
2. **No Key Logging**: Keys are never written to logs or exfiltrated.
3. **Session Management**: JWT-based authentication with 24h expiry.
4. **Credit System**: Users prepay credits; jobs deduct credits before execution.
5. **Ephemeral Decryption**: Keys decrypted only within the job execution scope.

## Revenue Model

- **$1 per wallet per mint**
- User pays upfront via crypto transfer
- Admin verifies payment on-chain
- Credits added to user account
- User launches job → credits deducted

## Setup Instructions

### 1. Install Dependencies
```bash
pip install -r requirements.txt
pip install -r web/requirements.txt
```

### 2. Configure Environment
```bash
# Generate secure keys
python -c "from cryptography.fernet import Fernet; import secrets; print('SECRET_KEY=' + secrets.token_hex(32)); print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())" > web/.env

# Then edit web/.env and add your settings:
# - TREASURY_ADDRESS=0xYourWalletAddress
# - TREASURY_PRIVATE_KEY=0xYourPrivateKey (for payment verification)
```

The `web/.env` file is required for the backend to start. A template is included at `web/deployment/.env.example` if you need the full list of options.

### 3. Run Server
```bash
python web/backend/main.py
# Or use uvicorn directly:
uvicorn web.backend.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 4. Access Dashboard
Open http://localhost:8000 in your browser.

## Production Deployment

### Docker
```bash
docker-compose -f web/deployment/docker-compose.yml up -d
```

### Nginx Reverse Proxy
```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### Database Migration (PostgreSQL)
```bash
# Install alembic
pip install alembic

# Initialize
alembic init alembic

# Configure alembic.ini with your DATABASE_URL
# Run migrations
alembic revision --autogenerate -m "Initial"
alembic upgrade head
```

## Admin Tasks

### Verify Payment
```python
from web.backend.database import SessionLocal, Payment
from web.backend.config import settings

db = SessionLocal()
payment = db.query(Payment).filter(Payment.tx_hash == "0x...").first()
if payment:
    payment.status = "completed"
    # Add credits to user
    payment.user.credits += payment.amount
    db.commit()
```

### Manual Credit Addition
```python
from web.backend.database import SessionLocal, User

db = SessionLocal()
user = db.query(User).filter(User.email == "user@example.com").first()
user.credits += 10.0  # Add $10 credits
db.commit()
```

## UI Features

### Landing Page
- Hero section with gradient text
- Feature cards with hover effects
- Pricing section
- Login/Register modal

### Dashboard
- Real-time stats (credits, jobs, mints, spent)
- 4-step wizard for creating jobs:
  1. Basic Info (contract, network, quantity, mode)
  2. Advanced Options (God Mode, Auto-Transfer, Sweeper)
  3. Worker Wallets (add private keys)
  4. Review & Pay
- Job list with status badges
- Real-time worker status updates (via WebSocket)

### Design System
- Black & white glossy theme
- Glassmorphism cards
- Smooth animations
- Responsive layout
- Inter font family

## Customization

### Change Price
Edit `web/backend/config.py`:
```python
PRICE_PER_WALLET_USDT = 2.0  # $2 per wallet
```

### Add Network
Edit `web/backend/main.py` `/api/networks` endpoint.

### Customize UI
Edit `web/frontend/assets/style.css` CSS variables.

## Monitoring

### Logs
```bash
# Application logs
tail -f uvicorn.log

# Job execution logs
tail -f sweetsnipe.log
```

### Health Check
```bash
curl http://localhost:8000/
# Should return HTML
```

## Security Checklist

- [ ] Change SECRET_KEY and ENCRYPTION_KEY to strong random values
- [ ] Enable HTTPS (Let's Encrypt / Cloudflare)
- [ ] Use PostgreSQL instead of SQLite for production
- [ ] Set up firewall (only ports 80, 443 open)
- [ ] Enable fail2ban for SSH
- [ ] Regular database backups
- [ ] Monitor for unusual activity
- [ ] Keep dependencies updated

## Legal Considerations

1. **Terms of Service**: Users must agree to terms before using
2. **Disclaimer**: Clearly state users should use burner wallets
3. **Privacy Policy**: How you handle user data
4. **Jurisdiction**: Check local laws regarding automated trading/minting
5. **KYC/AML**: Depending on volume and jurisdiction

## Support

For issues or questions, check the logs first:
- `bot_activity.log` - Bot execution logs
- `uvicorn.log` - Web server logs
- Database: `sweetsnipe.db` (SQLite)

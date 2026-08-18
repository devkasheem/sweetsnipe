# Sweetsnipe Hosted - Deployment Guide

## Quick Start

### Option 1: Docker (Recommended)
```bash
# Create .env file
cp web/deployment/.env.example web/deployment/.env

# Edit with your settings
nano web/deployment/.env

# Start
docker-compose -f web/deployment/docker-compose.yml up -d
```

### Option 2: Direct Python
```bash
# Install web requirements
pip install -r web/requirements.txt

# Set environment variables
export SECRET_KEY="your-secret-key"
export ENCRYPTION_KEY="your-encryption-key"
export TREASURY_ADDRESS="0xYourTreasuryAddress"

# Run
python web/backend/main.py
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Yes | JWT signing key (random string) |
| `ENCRYPTION_KEY` | Yes | Fernet encryption key for private keys |
| `DATABASE_URL` | No | Database URL (default: sqlite) |
| `TREASURY_ADDRESS` | Yes | Your wallet address for payments |
| `TREASURY_PRIVATE_KEY` | No | Private key for treasury (for verification) |
| `PRICE_PER_WALLET_USDT` | No | Price per wallet (default: 1.0) |

## Generate Keys
```bash
python -c "from cryptography.fernet import Fernet; print('SECRET_KEY:', 'your-jwt-secret-key-here'); print('ENCRYPTION_KEY:', Fernet.generate_key().decode())"
```

## Access
- Web UI: http://your-server:8000
- API Docs: http://your-server:8000/docs

## Security Notes
1. **Never commit .env files**
2. Use strong random SECRET_KEY and ENCRYPTION_KEY
3. Enable HTTPS in production (use nginx/caddy reverse proxy)
4. Regularly backup the database
5. Monitor for suspicious activity

## Payment Flow
1. User sends $1 equivalent to TREASURY_ADDRESS
2. User submits TX hash in dashboard
3. Admin verifies payment on-chain
4. Credits are added to user account
5. User creates mint job (deducts credits)

## Production Deployment
- Use PostgreSQL instead of SQLite
- Set up Redis for job queue scaling
- Use nginx/Caddy as reverse proxy with SSL
- Enable uvicorn workers: `uvicorn web.backend.main:app --workers 4`
- Set up monitoring (Prometheus + Grafana)
- Regular database backups

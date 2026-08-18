from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import timedelta, datetime
from typing import List, Dict, Optional
import asyncio
import json
import os
import sys
import logging
import logging.handlers
from slowapi import Limiter
from slowapi.util import get_remote_address
import jwt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".."))

from backend.database import SessionLocal, User, Job, Worker, Payment, SavedWallet, Base, engine
from backend.auth import get_password_hash, verify_password, create_access_token, get_current_user, get_db
from backend.schemas import UserCreate, UserLogin, Token, JobCreate, JobResponse, WorkerResponse, PaymentCreate, PaymentResponse, SavedWalletCreate, SavedWalletResponse, JobFilter
from backend.config import settings, encrypt_key, decrypt_key
from backend.job_queue import JobQueue
from backend.payment_verifier import payment_verifier

# ========== LOGGING SETUP ==========
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# File handler for audit logging
os.makedirs("logs", exist_ok=True)
file_handler = logging.handlers.RotatingFileHandler(
    'logs/audit.log',
    maxBytes=10_000_000,  # 10MB
    backupCount=10
)
logger.addHandler(file_handler)

app = FastAPI(title="Sweetsnipe Hosted", description="Enterprise NFT Minting Service")

# ========== SECURITY: Rate Limiting ==========
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])
app.state.limiter = limiter

# ========== SECURITY: CORS Configuration ==========
# SECURITY FIX: Environment-specific CORS origins
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8000").split(",")
if settings.ENV == "production":
    # Production: Only allow explicitly configured domains
    logger.info(f"Production CORS origins: {ALLOWED_ORIGINS}")
else:
    # Development: Allow localhost
    logger.info(f"Development CORS origins: {ALLOWED_ORIGINS}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ========== SECURITY: Security Headers Middleware ==========
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        forwarded_proto = request.headers.get("x-forwarded-proto", "").lower()
        if settings.ENV == "production" and forwarded_proto == "http":
            redirect_url = request.url.replace(scheme="https")
            return RedirectResponse(url=redirect_url, status_code=301)

        # Security headers
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        return response

app.add_middleware(SecurityHeadersMiddleware)

app.mount("/static", StaticFiles(directory="frontend/assets"), name="static")
templates = Jinja2Templates(directory="frontend/templates")

job_queue = JobQueue()

Base.metadata.create_all(bind=engine)

@app.on_event("startup")
async def startup_event():
    logger.info(f"🚀 Sweetsnipe server starting... (Environment: {settings.ENV})")
    job_queue.start()
    asyncio.create_task(periodic_payment_check())
    logger.info("✅ Server startup complete")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("🛑 Sweetsnipe server shutting down...")
    await job_queue.stop()
    logger.info("✅ Server shutdown complete")

async def periodic_payment_check():
    while True:
        try:
            db = SessionLocal()
            pending = db.query(Payment).filter(Payment.status == "pending").all()
            db.close()
            for payment in pending:
                asyncio.create_task(verify_payment_background(payment.id))
        except Exception as e:
            logger.error(f"Periodic check error: {e}")
        await asyncio.sleep(30)

@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/dashboard")
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request, "treasury_address": settings.TREASURY_ADDRESS})

@app.get("/admin")
async def admin_dashboard(request: Request):
    """Admin dashboard - requires authentication and admin role check in frontend JS"""
    return templates.TemplateResponse("admin.html", {"request": request, "treasury_address": settings.TREASURY_ADDRESS})

# ========== MONITORING & HEALTH ==========
@app.get("/api/health")
async def health_check():
    """
    Comprehensive health check endpoint for monitoring.
    Checks database, job queue, and basic system health.
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "environment": settings.ENV,
        "version": "1.0.0",
        "checks": {}
    }

    # Check database connectivity
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        health_status["checks"]["database"] = "ok"
    except Exception as e:
        health_status["checks"]["database"] = f"error: {str(e)[:50]}"
        health_status["status"] = "degraded"

    # Check job queue status
    try:
        health_status["checks"]["job_queue"] = "running" if job_queue.running else "stopped"
        if not job_queue.running:
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["checks"]["job_queue"] = f"error: {str(e)[:50]}"
        health_status["status"] = "degraded"

    return health_status

@app.post("/api/auth/register", response_model=Token)
@limiter.limit("5/minute")  # SECURITY: Rate limit registrations
async def register(request: Request, user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        logger.warning(f"Registration attempt for already registered email: {user.email}")
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = get_password_hash(user.password)
    db_user = User(email=user.email, hashed_password=hashed_password, credits=0.0)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    logger.info(f"New user registered: {user.email}")
    
    # Use short-lived tokens
    access_token_expires = timedelta(minutes=15)
    access_token = create_access_token(data={"sub": db_user.email}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/api/auth/token", response_model=Token)
@limiter.limit("10/minute")  # SECURITY: Rate limit login attempts
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        logger.warning(f"Failed login attempt for email: {form_data.username}")
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    logger.info(f"Successful login for user: {user.email}")
    
    # Use short-lived tokens
    access_token_expires = timedelta(minutes=15)
    access_token = create_access_token(data={"sub": user.email}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/auth/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    return {
        "email": current_user.email,
        "credits": current_user.credits,
        "is_admin": current_user.is_admin,
        "is_active": current_user.is_active
    }

@app.post("/api/payments", response_model=PaymentResponse)
@limiter.limit("5/minute")  # SECURITY FIX: Rate limit payment submissions
async def create_payment(request: Request, payment: PaymentCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    existing = db.query(Payment).filter(Payment.tx_hash == payment.tx_hash).first()
    if existing:
        raise HTTPException(status_code=400, detail="Transaction hash already submitted")
    
    db_payment = Payment(
        user_id=current_user.id,
        tx_hash=payment.tx_hash,
        amount=payment.amount,
        currency=payment.currency,
        network=payment.network,
        status="pending"
    )
    db.add(db_payment)
    db.commit()
    db.refresh(db_payment)
    
    asyncio.create_task(verify_payment_background(db_payment.id))
    
    return db_payment

@app.get("/api/payments", response_model=List[PaymentResponse])
async def get_payments(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    payments = db.query(Payment).filter(Payment.user_id == current_user.id).order_by(Payment.created_at.desc()).all()
    return payments

async def verify_payment_background(payment_id: str):
    db = SessionLocal()
    try:
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment or payment.status != "pending":
            return
        
        is_valid, error = await payment_verifier.verify_payment(
            payment.tx_hash,
            payment.amount,
            payment.currency
        )
        
        if is_valid:
            payment.status = "completed"
            payment.verified_at = datetime.utcnow()
            payment.user.credits += payment.amount
        else:
            payment.status = "failed"
            payment.error_message = error
        
        db.commit()
    except Exception as e:
        logger.error(f"Background payment verification failed: {e}")
    finally:
        db.close()

# ========== SECURITY: Admin Role Check ==========
async def is_admin(current_user: User = Depends(get_current_user)) -> User:
    """SECURITY: Verify user has admin role."""
    if not current_user.is_admin:
        logger.warning(f"Unauthorized admin access attempt by user: {current_user.email}")
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )
    return current_user

@app.post("/api/admin/recheck-payments")
async def recheck_pending_payments(admin: User = Depends(is_admin), db: Session = Depends(get_db)):
    """SECURITY: Admin-only endpoint to recheck pending payments."""
    logger.info(f"Admin {admin.email} initiated payment recheck")

    pending = db.query(Payment).filter(Payment.status == "pending").all()
    count = 0
    for payment in pending:
        asyncio.create_task(verify_payment_background(payment.id))
        count += 1

    logger.info(f"Rechecking {count} pending payments initiated by admin {admin.email}")
    return {"message": f"Rechecking {count} pending payments"}

# ========== ADMIN ENDPOINTS ==========

@app.get("/api/admin/users")
async def get_all_users(admin: User = Depends(is_admin), db: Session = Depends(get_db)):
    """Get all users with their stats."""
    from sqlalchemy import func

    users = db.query(User).all()
    result = []
    for user in users:
        job_count = db.query(func.count(Job.id)).filter(Job.user_id == user.id).scalar()
        result.append({
            "id": user.id,
            "email": user.email,
            "credits": user.credits,
            "is_active": user.is_active,
            "is_admin": user.is_admin,
            "created_at": user.created_at,
            "job_count": job_count
        })
    return result

@app.get("/api/admin/jobs")
async def get_all_jobs(
    admin: User = Depends(is_admin),
    db: Session = Depends(get_db),
    status: Optional[str] = None
):
    """Get all jobs from all users."""
    query = db.query(Job)

    if status:
        query = query.filter(Job.status == status)

    jobs = query.order_by(Job.created_at.desc()).all()
    result = []
    for job in jobs:
        user = db.query(User).filter(User.id == job.user_id).first()
        result.append({
            "id": job.id,
            "user_id": job.user_id,
            "user_email": user.email if user else "Unknown",
            "nft_contract": job.nft_contract,
            "network": job.network,
            "mint_quantity": job.mint_quantity,
            "total_wallets": job.total_wallets,
            "successful_mints": job.successful_mints,
            "failed_mints": job.failed_mints,
            "status": job.status,
            "cost": job.cost,
            "created_at": job.created_at,
            "completed_at": job.completed_at
        })
    return result

@app.get("/api/admin/payments")
async def get_all_payments(admin: User = Depends(is_admin), db: Session = Depends(get_db)):
    """Get all payments from all users."""
    payments = db.query(Payment).order_by(Payment.created_at.desc()).all()
    result = []
    for payment in payments:
        user = db.query(User).filter(User.id == payment.user_id).first()
        result.append({
            "id": payment.id,
            "user_id": payment.user_id,
            "user_email": user.email if user else "Unknown",
            "tx_hash": payment.tx_hash,
            "amount": payment.amount,
            "currency": payment.currency,
            "network": payment.network,
            "status": payment.status,
            "created_at": payment.created_at,
            "verified_at": payment.verified_at
        })
    return result

@app.get("/api/admin/activity")
async def get_activity_log(admin: User = Depends(is_admin), db: Session = Depends(get_db)):
    """Get recent activity log."""
    # Get recent jobs, payments, and user registrations
    activities = []

    # Recent jobs
    recent_jobs = db.query(Job).order_by(Job.created_at.desc()).limit(5).all()
    for job in recent_jobs:
        user = db.query(User).filter(User.id == job.user_id).first()
        activities.append({
            "action": "Job Created",
            "details": f"{user.email if user else 'Unknown'} created job for {job.nft_contract[:10]}...",
            "timestamp": job.created_at
        })

    # Recent payments
    recent_payments = db.query(Payment).order_by(Payment.created_at.desc()).limit(5).all()
    for payment in recent_payments:
        user = db.query(User).filter(User.id == payment.user_id).first()
        activities.append({
            "action": "Payment Submitted",
            "details": f"{user.email if user else 'Unknown'} submitted ${payment.amount} payment",
            "timestamp": payment.created_at
        })

    # Recent users
    recent_users = db.query(User).order_by(User.created_at.desc()).limit(5).all()
    for user in recent_users:
        if not user.is_admin:  # Don't show admin users in activity
            activities.append({
                "action": "New User Registered",
                "details": f"{user.email} joined the platform",
                "timestamp": user.created_at
            })

    # Sort by timestamp
    activities.sort(key=lambda x: x["timestamp"], reverse=True)
    return activities[:20]

@app.post("/api/admin/users/{user_id}/credits")
async def adjust_user_credits(
    user_id: str,
    admin: User = Depends(is_admin),
    db: Session = Depends(get_db),
    amount: float = 0.0
):
    """Adjust user credits (add or subtract)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.credits += amount
    if user.credits < 0:
        user.credits = 0.0

    db.commit()
    logger.info(f"Admin {admin.email} adjusted credits for {user.email} by {amount}")
    return {"message": f"Credits adjusted to {user.credits}", "new_balance": user.credits}

@app.post("/api/admin/users/{user_id}/status")
async def toggle_user_status(
    user_id: str,
    admin: User = Depends(is_admin),
    db: Session = Depends(get_db),
    is_active: bool = True
):
    """Activate or deactivate a user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = is_active
    db.commit()
    logger.info(f"Admin {admin.email} {'activated' if is_active else 'deactivated'} user {user.email}")
    return {"message": f"User {'activated' if is_active else 'deactivated'}", "is_active": user.is_active}

@app.post("/api/admin/payments/{payment_id}/verify")
async def force_verify_payment(
    payment_id: str,
    admin: User = Depends(is_admin),
    db: Session = Depends(get_db)
):
    """Force verification of a pending payment."""
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    asyncio.create_task(verify_payment_background(payment_id))
    logger.info(f"Admin {admin.email} initiated verification for payment {payment_id}")
    return {"message": "Payment verification initiated"}

@app.get("/api/admin/logs")
async def get_audit_logs(admin: User = Depends(is_admin)):
    """Get recent audit logs."""
    import os
    log_file = "logs/audit.log"

    if not os.path.exists(log_file):
        return "No logs available"

    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
            # Return last 100 lines
            return ''.join(lines[-100:])
    except Exception as e:
        return f"Error reading logs: {str(e)}"

@app.post("/api/jobs", response_model=JobResponse)
@limiter.limit("10/minute")  # SECURITY FIX: Rate limit job creation
async def create_job(request: Request, job: JobCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cost = len(job.workers) * settings.PRICE_PER_WALLET_USDT
    if current_user.credits < cost:
        raise HTTPException(status_code=400, detail=f"Insufficient credits. Need {cost}, have {current_user.credits}")
    
    db_job = Job(
        user_id=current_user.id,
        nft_contract=job.nft_contract,
        network=job.network,
        mint_quantity=job.mint_quantity,
        mint_mode=job.mint_mode,
        mint_func_name=job.mint_func_name,
        recipient_address=job.recipient_address,
        presign_enabled=job.presign_enabled,
        auto_transfer_enabled=job.auto_transfer_enabled,
        auto_sweep_enabled=job.auto_sweep_enabled,
        total_wallets=len(job.workers),
        cost=cost,
        status="queued"
    )
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    
    for worker_data in job.workers:
        if worker_data.private_key:
            encrypted_key = encrypt_key(worker_data.private_key)
            proxy_url = worker_data.proxy_url
        elif worker_data.wallet_id:
            saved_wallet = db.query(SavedWallet).filter(SavedWallet.id == worker_data.wallet_id, SavedWallet.user_id == current_user.id).first()
            if not saved_wallet:
                raise HTTPException(status_code=400, detail=f"Saved wallet {worker_data.wallet_id} not found")
            encrypted_key = saved_wallet.encrypted_private_key
            proxy_url = worker_data.proxy_url or saved_wallet.proxy_url
        else:
            raise HTTPException(status_code=400, detail="Worker must have either private_key or wallet_id")
        
        db_worker = Worker(
            job_id=db_job.id,
            encrypted_private_key=encrypted_key,
            proxy_url=proxy_url,
            status="queued"
        )
        db.add(db_worker)
    
    current_user.credits -= cost
    db.commit()
    
    job_queue.add_job(db_job.id)
    
    return db_job

@app.get("/api/jobs", response_model=List[JobResponse])
async def get_jobs(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    jobs = db.query(Job).filter(Job.user_id == current_user.id).order_by(Job.created_at.desc()).all()
    return jobs

@app.get("/api/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@app.get("/api/jobs/{job_id}/workers", response_model=List[WorkerResponse])
async def get_job_workers(job_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    workers = db.query(Worker).filter(Worker.job_id == job_id).all()
    return workers

@app.get("/api/networks")
async def get_networks():
    return {
        "ETH": {"name": "Ethereum", "symbol": "ETH", "id": 1},
        "BASE": {"name": "Base", "symbol": "ETH", "id": 8453},
        "OP": {"name": "Optimism", "symbol": "ETH", "id": 10},
        "ARB": {"name": "Arbitrum", "symbol": "ETH", "id": 42161},
        "POLY": {"name": "Polygon", "symbol": "POL", "id": 137},
        "BSC": {"name": "BNB Chain", "symbol": "BNB", "id": 56},
        "AVAX": {"name": "Avalanche", "symbol": "AVAX", "id": 43114},
        "BERA": {"name": "Berachain", "symbol": "BERA", "id": 80085},
    }

# Wallet Library Endpoints
@app.post("/api/wallets", response_model=SavedWalletResponse)
async def create_wallet(wallet: SavedWalletCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from eth_account import Account
    try:
        acct = Account.from_key(wallet.private_key)
        address = acct.address
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid private key")
    
    encrypted_key = encrypt_key(wallet.private_key)
    db_wallet = SavedWallet(
        user_id=current_user.id,
        encrypted_private_key=encrypted_key,
        address=address,
        proxy_url=wallet.proxy_url,
        label=wallet.label
    )
    db.add(db_wallet)
    db.commit()
    db.refresh(db_wallet)
    return db_wallet

@app.get("/api/wallets", response_model=List[SavedWalletResponse])
async def get_wallets(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    wallets = db.query(SavedWallet).filter(SavedWallet.user_id == current_user.id).all()
    return wallets

@app.delete("/api/wallets/{wallet_id}")
async def delete_wallet(wallet_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    wallet = db.query(SavedWallet).filter(SavedWallet.id == wallet_id, SavedWallet.user_id == current_user.id).first()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    db.delete(wallet)
    db.commit()
    return {"message": "Wallet deleted"}

@app.post("/api/wallets/bulk", response_model=List[SavedWalletResponse])
async def bulk_import_wallets(wallets: List[SavedWalletCreate], current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from eth_account import Account
    imported = []
    for wallet in wallets:
        try:
            acct = Account.from_key(wallet.private_key)
            address = acct.address
        except Exception:
            continue
        
        encrypted_key = encrypt_key(wallet.private_key)
        db_wallet = SavedWallet(
            user_id=current_user.id,
            encrypted_private_key=encrypted_key,
            address=address,
            proxy_url=wallet.proxy_url,
            label=wallet.label
        )
        db.add(db_wallet)
        imported.append(db_wallet)
    
    db.commit()
    for w in imported:
        db.refresh(w)
    return imported

# Job History with Filtering
@app.get("/api/jobs/filtered", response_model=List[JobResponse])
async def get_filtered_jobs(
    status: Optional[str] = None,
    network: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    query = db.query(Job).filter(Job.user_id == current_user.id)
    
    if status:
        query = query.filter(Job.status == status)
    if network:
        query = query.filter(Job.network == network)
    if start_date:
        query = query.filter(Job.created_at >= start_date)
    if end_date:
        query = query.filter(Job.created_at <= end_date)
    if search:
        query = query.filter(Job.nft_contract.contains(search))
    
    jobs = query.order_by(Job.created_at.desc()).all()
    return jobs

@app.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    # SECURITY FIX: WebSocket authentication
    # Extract token from query parameters
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing authentication token")
        return

    # Verify token and get user
    db = SessionLocal()
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        email: str = payload.get("sub")
        if not email:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
            return

        user = db.query(User).filter(User.email == email).first()
        if not user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="User not found")
            return

        # Verify user owns this job
        job = db.query(Job).filter(Job.id == job_id, Job.user_id == user.id).first()
        if not job:
            await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA, reason="Job not found or access denied")
            return

        await websocket.accept()
        await job_queue.register(job_id, websocket)

        try:
            while True:
                data = await websocket.receive_text()
        except WebSocketDisconnect:
            await job_queue.unregister(job_id, websocket)
    except jwt.PyJWTError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
    finally:
        db.close()

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", str(settings.PORT)))
    uvicorn.run(app, host="0.0.0.0", port=port)

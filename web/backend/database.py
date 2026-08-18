from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.pool import QueuePool, NullPool
from datetime import datetime
import uuid
import os

# PRODUCTION FIX: Support both SQLite (dev) and PostgreSQL (production)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sweetsnipe.db")

# Configure engine based on database type
if DATABASE_URL.startswith("sqlite"):
    # SQLite: Single-threaded, no connection pooling
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=NullPool
    )
else:
    # PostgreSQL/MySQL: Production with connection pooling
    engine = create_engine(
        DATABASE_URL,
        poolclass=QueuePool,
        pool_size=20,  # Max 20 connections
        max_overflow=10,  # Allow 10 extra connections during spikes
        pool_pre_ping=True,  # Verify connections before use
        pool_recycle=3600,  # Recycle connections after 1 hour
        echo=False
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    credits = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)  # SECURITY: Admin role for privileged operations
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    jobs = relationship("Job", back_populates="user")

    __table_args__ = (
        Index('idx_user_email_active', 'email', 'is_active'),
    )

class Job(Base):
    __tablename__ = "jobs"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    nft_contract = Column(String, nullable=False, index=True)
    network = Column(String, nullable=False, index=True)
    mint_quantity = Column(Integer, nullable=False)
    mint_mode = Column(String, nullable=False)
    mint_func_name = Column(String, nullable=True)
    recipient_address = Column(String, nullable=True)
    presign_enabled = Column(Boolean, default=False)
    auto_transfer_enabled = Column(Boolean, default=False)
    auto_sweep_enabled = Column(Boolean, default=False)
    status = Column(String, default="pending", index=True)
    total_wallets = Column(Integer, nullable=False)
    successful_mints = Column(Integer, default=0)
    failed_mints = Column(Integer, default=0)
    cost = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    user = relationship("User", back_populates="jobs")
    workers = relationship("Worker", back_populates="job", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_job_user_status', 'user_id', 'status'),
        Index('idx_job_status_created', 'status', 'created_at'),
    )

class Worker(Base):
    __tablename__ = "workers"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey("jobs.id"), nullable=False)
    encrypted_private_key = Column(Text, nullable=False)
    proxy_url = Column(String, nullable=True)
    status = Column(String, default="pending")
    balance = Column(String, nullable=True)
    tx_hash = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    job = relationship("Job", back_populates="workers")

class Payment(Base):
    __tablename__ = "payments"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    tx_hash = Column(String, unique=True, nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, nullable=False)
    network = Column(String, nullable=False, default="ETH")
    status = Column(String, default="pending")
    error_message = Column(String, nullable=True)
    verification_method = Column(String, default="blockchain")  # SECURITY: Track verification method
    verification_attempts = Column(Integer, default=0)  # SECURITY: Track attempts
    last_check_at = Column(DateTime, nullable=True)  # SECURITY: Track last check time
    created_at = Column(DateTime, default=datetime.utcnow)
    verified_at = Column(DateTime, nullable=True)

class SavedWallet(Base):
    __tablename__ = "saved_wallets"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    encrypted_private_key = Column(Text, nullable=False)
    address = Column(String, nullable=False)
    proxy_url = Column(String, nullable=True)
    label = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="saved_wallets")

User.saved_wallets = relationship("SavedWallet", back_populates="user", cascade="all, delete-orphan")

Base.metadata.create_all(bind=engine)

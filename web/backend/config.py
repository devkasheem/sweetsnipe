import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import field_validator
from cryptography.fernet import Fernet
import logging

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    SECRET_KEY: str = ""
    ENCRYPTION_KEY: str = ""
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///./sweetsnipe.db"
    )
    PORT: int = int(os.getenv("PORT", "8000"))
    TREASURY_ADDRESS: str = ""
    TREASURY_PRIVATE_KEY: str = ""
    PRICE_PER_WALLET_USDT: float = 1.0
    TREASURY_NETWORK: str = "ETH"
    ENV: str = "development"  # development, staging, production
    DEBUG: bool = False

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, v):
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.strip().lower() in ("true", "1", "yes", "on", "debug")
        return bool(v)

    @property
    def is_debug(self) -> bool:
        return self.DEBUG
    
    RPC_NETWORKS: dict = {
        "ETH": ["https://eth.llamarpc.com", "https://rpc.ankr.com/eth", "https://ethereum.publicnode.com"],
        "BASE": ["https://mainnet.base.org", "https://base.llamarpc.com", "https://base.publicnode.com"],
        "OP": ["https://mainnet.optimism.io", "https://optimism.llamarpc.com", "https://rpc.ankr.com/optimism"],
        "ARB": ["https://arb1.arbitrum.io/rpc", "https://arbitrum.llamarpc.com", "https://rpc.ankr.com/arbitrum"],
        "POLY": ["https://polygon-rpc.com", "https://polygon.llamarpc.com", "https://1rpc.io/matic"],
        "BSC": ["https://binance.llamarpc.com", "https://bsc-dataseed.binance.org", "https://rpc.ankr.com/bsc"],
        "AVAX": ["https://api.avax.network/ext/bc/C/rpc", "https://avalanche.public-rpc.com"],
        "BERA": ["https://artio.rpc.berachain.com", "https://rpc.berachain.com"],
    }
    
    class Config:
        env_file = str(BASE_DIR / ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()

# ========== SECURITY: Validate Required Secrets ==========
def validate_secrets():
    """Validate that all required secrets are properly configured."""
    errors = []

    print("=" * 60)
    print("CONFIG DEBUG - Raw os.environ relevant keys:")
    for key in ["ENV", "SECRET_KEY", "ENCRYPTION_KEY", "TREASURY_ADDRESS", "TREASURY_PRIVATE_KEY", "DATABASE_URL", "ALLOWED_ORIGINS", "PORT"]:
        val = os.environ.get(key, "(not set)")
        if key in ["SECRET_KEY", "ENCRYPTION_KEY", "TREASURY_PRIVATE_KEY"] and val != "(not set)":
            val = val[:10] + "..." if len(val) > 10 else val
        print(f"  {key}: {val}")
    print("=" * 60)
    print(f"  settings.ENV: {settings.ENV}")
    print(f"  settings.TREASURY_ADDRESS: '{settings.TREASURY_ADDRESS}'")
    print("=" * 60)

    if not settings.SECRET_KEY or "change-me" in settings.SECRET_KEY.lower():
        errors.append("SECRET_KEY is not set or contains default value in .env")

    if not settings.ENCRYPTION_KEY or "change-me" in settings.ENCRYPTION_KEY.lower():
        errors.append("ENCRYPTION_KEY is not set or contains default value in .env")

    if settings.ENV == "production":
        treasury_address = settings.TREASURY_ADDRESS.strip()
        if not treasury_address or not treasury_address.startswith("0x") or len(treasury_address) != 42:
            errors.append("TREASURY_ADDRESS not configured for production")

        if settings.TREASURY_PRIVATE_KEY.strip():
            treasury_private_key = settings.TREASURY_PRIVATE_KEY.strip()
            normalized_key = treasury_private_key[2:] if treasury_private_key.startswith("0x") else treasury_private_key
            if len(normalized_key) != 64 or any(ch not in "0123456789abcdefABCDEF" for ch in normalized_key):
                errors.append("TREASURY_PRIVATE_KEY has invalid format (expected 0x followed by 64 hex chars)")

    if errors:
        error_msg = "CONFIGURATION ERROR - Server cannot start:\n" + "\n".join([f"  ❌ {e}" for e in errors])
        raise RuntimeError(error_msg)

# Validate on import
validate_secrets()

cipher = None
try:
    cipher = Fernet(settings.ENCRYPTION_KEY.encode())
except Exception as e:
    raise RuntimeError(f"ENCRYPTION_KEY is invalid or corrupted: {e}")

def encrypt_key(private_key: str) -> str:
    """Encrypt a private key using Fernet."""
    if cipher is None:
        raise RuntimeError("ENCRYPTION_KEY is not configured")
    return cipher.encrypt(private_key.encode()).decode()

def decrypt_key(encrypted_key: str) -> str:
    """Decrypt an encrypted private key."""
    if cipher is None:
        raise RuntimeError("ENCRYPTION_KEY is not configured")
    return cipher.decrypt(encrypted_key.encode()).decode()

from pydantic import BaseModel, EmailStr, field_validator, conint
from datetime import datetime
from typing import Optional, List

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    
    @field_validator('password')
    @classmethod
    def password_strength(cls, v):
        """SECURITY: Enforce minimum password requirements."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class WorkerCreate(BaseModel):
    private_key: Optional[str] = None
    wallet_id: Optional[str] = None
    proxy_url: Optional[str] = None

class JobCreate(BaseModel):
    nft_contract: str
    network: str
    mint_quantity: conint(gt=0, le=100)  # SECURITY: Max 100 per wallet
    mint_mode: str = "DIRECT"
    mint_func_name: str = "mint"
    recipient_address: Optional[str] = None
    presign_enabled: bool = False
    auto_transfer_enabled: bool = False
    auto_sweep_enabled: bool = False
    workers: List[WorkerCreate]
    max_threads: conint(gt=0, le=50) = 5  # SECURITY: Max threads limit

    @field_validator('nft_contract', 'recipient_address')
    @classmethod
    def validate_eth_address(cls, v):
        """SECURITY: Validate Ethereum address format."""
        if v is None:
            return v
        if not v.startswith('0x') or len(v) != 42:
            raise ValueError('Invalid Ethereum address format (must be 0x followed by 40 hex chars)')
        try:
            int(v, 16)
        except ValueError:
            raise ValueError('Invalid Ethereum address - not valid hex')
        return v.lower()

    @field_validator('network')
    @classmethod
    def validate_network(cls, v):
        """SECURITY: Validate network is in allowed list."""
        valid_networks = ['ETH', 'BASE', 'OP', 'ARB', 'POLY', 'BSC', 'AVAX', 'BERA']
        if v not in valid_networks:
            raise ValueError(f'Network must be one of: {valid_networks}')
        return v
    
    @field_validator('mint_mode')
    @classmethod
    def validate_mint_mode(cls, v):
        """SECURITY: Validate mint mode is in allowed list."""
        valid_modes = ['DIRECT', 'PROXY']
        if v not in valid_modes:
            raise ValueError(f'Mint mode must be one of: {valid_modes}')
        return v

class JobResponse(BaseModel):
    id: str
    nft_contract: str
    network: str
    mint_quantity: int
    mint_mode: str
    status: str
    total_wallets: int
    successful_mints: int
    failed_mints: int
    cost: float
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class WorkerResponse(BaseModel):
    id: str
    status: str
    balance: Optional[str]
    tx_hash: Optional[str]
    error_message: Optional[str]
    
    class Config:
        from_attributes = True

class PaymentCreate(BaseModel):
    tx_hash: str
    amount: float
    currency: str = "ETH"
    network: str = "ETH"
    
    @field_validator('tx_hash')
    @classmethod
    def validate_tx_hash(cls, v):
        """SECURITY: Validate transaction hash format."""
        if not v.startswith('0x') or len(v) != 66:
            raise ValueError('Invalid transaction hash format')
        return v.lower()
    
    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v):
        """SECURITY: Validate amount is positive."""
        if v <= 0:
            raise ValueError('Amount must be greater than 0')
        if v > 1_000_000:  # Sanity check: max 1M per transaction
            raise ValueError('Amount exceeds maximum allowed')
        return v

class PaymentResponse(BaseModel):
    id: str
    amount: float
    currency: str
    network: str
    status: str
    error_message: Optional[str]
    created_at: datetime
    verified_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class SavedWalletCreate(BaseModel):
    private_key: str
    proxy_url: Optional[str] = None
    label: Optional[str] = None
    
    @field_validator('label')
    @classmethod
    def validate_label(cls, v):
        """SECURITY: Limit label length to prevent injection."""
        if v and len(v) > 100:
            raise ValueError('Label must be 100 characters or less')
        return v

class SavedWalletResponse(BaseModel):
    id: str
    address: str
    proxy_url: Optional[str]
    label: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

class JobFilter(BaseModel):
    status: Optional[str] = None
    network: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    search: Optional[str] = None

"""
Shared constants across the application.
Replaces magic numbers with named constants.
"""

# Gas calculation multipliers
GAS_ESTIMATE_BUFFER = 1.2  # Add 20% buffer to gas estimates
GAS_PRICE_BUFFER = 1.1  # Add 10% buffer to gas price
EIP1559_BASE_FEE_MULTIPLIER = 1.5  # Multiply base fee by 1.5 for maxFeePerGas
EIP1559_PRIORITY_FEE_MULTIPLIER = 1.5  # Multiply priority fee by 1.5

# Pre-signed transaction settings
PRESIGN_TIME_BEFORE_MINT = 5  # Seconds before mint to prepare transaction
PRESIGN_DEFAULT_GAS_MULTIPLIER = 2.0  # Default gas price multiplier for pre-signed tx
PRESIGN_DEFAULT_GAS_LIMIT = 300000  # Default gas limit for pre-signed tx

# Retry and timeout settings
DEFAULT_RETRY_DELAY_MIN = 1.0  # Minimum retry delay in seconds
DEFAULT_RETRY_DELAY_MAX = 3.0  # Maximum retry delay in seconds
TRANSACTION_RECEIPT_TIMEOUT = 120  # Seconds to wait for transaction receipt
MAX_RETRY_ATTEMPTS = 50  # Maximum retry attempts before giving up
MAX_EXECUTION_TIME = 3600  # Maximum execution time in seconds (1 hour)

# RPC and network settings
RPC_TIMEOUT = 30  # RPC request timeout in seconds
RPC_RETRY_DELAY = 2.0  # Delay before rotating RPC provider

# Gas settings
DEFAULT_GAS_LIMIT = 400000  # Default gas limit for transactions
TRANSFER_GAS_LIMIT = 150000  # Gas limit for NFT transfers
ETH_TRANSFER_GAS_LIMIT = 21000  # Gas limit for ETH transfers
DEFAULT_MAX_GAS_LIMIT_GWEI = 100.0  # Default maximum gas price in Gwei

# Funding settings
DEFAULT_MIN_WORKER_BALANCE = 0.005  # ETH
DEFAULT_FUNDING_AMOUNT = 0.01  # ETH
DEFAULT_MIN_SWEEP_AMOUNT = 0.005  # ETH

# Web3 settings
WEI_PER_ETH = 1e18
GWEI_PER_ETH = 1e9

# Cache TTL (seconds)
GAS_PRICE_CACHE_TTL = 10  # Cache gas price for 10 seconds
CONTRACT_METADATA_CACHE_TTL = 3600  # Cache contract metadata for 1 hour
NETWORK_METADATA_CACHE_TTL = 86400  # Cache network metadata for 24 hours

# WebSocket settings
WS_UPDATE_INTERVAL = 0.25  # Seconds between WebSocket updates

# UI settings
TUI_REFRESH_RATE = 4  # Refreshes per second for TUI
MAX_SYSTEM_LOGS = 8  # Maximum system log entries to display

# Security settings
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 15  # Short-lived tokens
PASSWORD_MIN_LENGTH = 8
MAX_LOGIN_ATTEMPTS = 5

# Rate limiting (requests per minute)
RATE_LIMIT_REGISTER = "5/minute"
RATE_LIMIT_LOGIN = "10/minute"
RATE_LIMIT_JOB_CREATE = "10/minute"
RATE_LIMIT_PAYMENT = "5/minute"
RATE_LIMIT_DEFAULT = "100/minute"

# Payment settings
DEFAULT_PRICE_PER_WALLET_USDT = 1.0  # $1 per wallet
PAYMENT_VERIFICATION_CONFIRMATIONS = 3  # Block confirmations required
PAYMENT_CHECK_INTERVAL = 30  # Seconds between payment verification checks

# Database connection pool settings
DB_POOL_SIZE = 20  # Maximum number of database connections
DB_MAX_OVERFLOW = 10  # Additional connections during spikes
DB_POOL_RECYCLE = 3600  # Recycle connections after 1 hour (seconds)

# Job queue settings
JOB_QUEUE_POLL_INTERVAL = 1.0  # Seconds between job queue polls
MAX_CONCURRENT_JOBS = 5  # Maximum jobs running simultaneously

# Validation
ETHEREUM_ADDRESS_LENGTH = 42  # "0x" + 40 hex characters
ETHEREUM_PRIVATE_KEY_LENGTH = 66  # "0x" + 64 hex characters

# Allowed mint function names (security whitelist)
ALLOWED_MINT_FUNCTIONS = [
    "mint",
    "publicMint",
    "purchase",
    "claim",
    "mintPublic",
    "safeMint",
    "mintToken",
    "mintNFT"
]

# HTTP settings
HTTP_TIMEOUT = 30  # Seconds
MAX_RETRIES = 3

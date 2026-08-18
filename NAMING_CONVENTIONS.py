"""
Comprehensive naming consistency refactoring guide.
Standardizes naming conventions across the codebase.
"""

# NAMING CONVENTIONS GUIDE

"""
1. VARIABLES & PARAMETERS
   - Use snake_case for all variables and function parameters
   - Be descriptive but concise

   ❌ BAD:
   pk = "0x123"
   uid = 1
   cfg = Config()
   w3 = Web3()

   ✅ GOOD:
   private_key = "0x123"
   worker_id = 1
   config = Config()
   web3_instance = Web3()

2. FUNCTIONS & METHODS
   - Use snake_case
   - Start with verb for actions
   - Be descriptive about what they do

   ❌ BAD:
   def checkGuard()
   def doMint()
   def proc()

   ✅ GOOD:
   def verify_contract_safety()
   def execute_mint_transaction()
   def process_job_queue()

3. CLASSES
   - Use PascalCase
   - Singular nouns for most classes
   - End with descriptive suffix for specific types

   ❌ BAD:
   class execution_unit
   class Executor

   ✅ GOOD:
   class ExecutionUnit
   class TransactionExecutor
   class GasOracle (service suffix implied)

4. CONSTANTS
   - Use UPPER_SNAKE_CASE
   - Group related constants with prefixes

   ❌ BAD:
   gasLimit = 300000
   maxWorkers = 5

   ✅ GOOD:
   GAS_LIMIT_DEFAULT = 300000
   MAX_WORKERS_CONCURRENT = 5

5. PRIVATE METHODS/ATTRIBUTES
   - Prefix with single underscore

   ❌ BAD:
   def rotateProvider()
   self.localNonce = None

   ✅ GOOD:
   def _rotate_provider()
   self._local_nonce = None

6. WEB3 RELATED
   - Always use full descriptive names

   ❌ BAD:
   w3, pk, addr, tx, rcpt

   ✅ GOOD:
   web3_instance, private_key, address, transaction, receipt

7. DATABASE MODELS
   - PascalCase for class names
   - snake_case for column names
   - Descriptive relationship names

   ✅ GOOD:
   class User(Base):
       user_id = Column(String)
       email_address = Column(String)
       hashed_password = Column(String)

       jobs = relationship("Job", back_populates="user")

8. API ENDPOINTS
   - Use kebab-case in URLs
   - RESTful naming

   ✅ GOOD:
   /api/jobs
   /api/auth/verify-email
   /api/user/saved-wallets

9. CONFIGURATION
   - UPPER_SNAKE_CASE for environment variables
   - snake_case for config object attributes

   ✅ GOOD:
   DATABASE_URL = os.getenv("DATABASE_URL")
   config.max_retry_attempts = 50

10. BOOLEAN VARIABLES
    - Use is_, has_, can_, should_ prefixes

    ❌ BAD:
    active = True
    verified = False

    ✅ GOOD:
    is_active = True
    has_verified = False
    can_execute = True
    should_retry = False
"""

# REFACTORING CHECKLIST

REFACTORING_TASKS = """
Files to refactor for naming consistency:

HIGH PRIORITY (Core execution):
✅ src/engine/execution.py - Already refactored
   - _pk → _private_key
   - _uid → _worker_id
   - _cfg → _config
   - w3 → web3_instance

MEDIUM PRIORITY (Services):
□ src/features/funder.py
   - pk → private_key
   - cfg → config
   - w3 → web3_instance

□ src/features/transfer.py
   - acct → account
   - w3 → web3_instance
   - uid → worker_id

□ src/ui/logger.py
   - Clean naming already, minimal changes

LOW PRIORITY (UI):
□ src/ui/dashboard.py
   - uid → worker_id
   - bal → balance

COMPLETED:
✅ All new shared modules use consistent naming
✅ src/shared/constants.py - All UPPER_SNAKE_CASE
✅ src/shared/validators.py - All snake_case
✅ src/shared/gas_oracle.py - Consistent naming
✅ src/core/execution_service.py - Proper naming throughout
"""

print(REFACTORING_TASKS)

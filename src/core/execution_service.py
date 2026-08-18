"""
Shared execution service layer - decouples CLI from web.
Provides a unified interface for minting operations.
"""
import asyncio
from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum
from web3 import AsyncWeb3

from src.shared.constants import MAX_RETRY_ATTEMPTS, MAX_EXECUTION_TIME
from src.shared.circuit_breaker import with_retry_and_timeout
from src.shared.gas_oracle import gas_oracle
from src.shared.validators import validator, ValidationError


class JobStatus(Enum):
    """Job status enumeration"""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class WorkerConfig:
    """Configuration for a single worker"""
    private_key: str
    proxy_url: Optional[str] = None
    worker_id: Optional[int] = None


@dataclass
class MintConfiguration:
    """Configuration for a minting job"""
    network: str
    nft_contract: str
    mint_quantity: int
    mint_mode: str  # "DIRECT" or "PROXY"
    mint_func_name: str = "mint"
    recipient_address: Optional[str] = None
    presign_enabled: bool = False
    auto_transfer_enabled: bool = False
    auto_sweep_enabled: bool = False
    gas_gwei: Optional[float] = None
    max_gas_limit: float = 100.0


@dataclass
class WorkerResult:
    """Result from a single worker execution"""
    worker_id: int
    status: str  # "success" or "failed"
    tx_hash: Optional[str] = None
    error_message: Optional[str] = None
    gas_used: Optional[int] = None
    balance_remaining: Optional[str] = None


@dataclass
class ExecutionResult:
    """Result from entire job execution"""
    job_id: str
    status: JobStatus
    workers: List[WorkerResult]
    successful_mints: int
    failed_mints: int
    total_gas_cost: float
    duration_seconds: float


class ExecutionCallbacks:
    """Callbacks for execution events"""

    def __init__(self):
        self.on_job_started: Optional[Callable] = None
        self.on_job_completed: Optional[Callable] = None
        self.on_worker_started: Optional[Callable] = None
        self.on_worker_completed: Optional[Callable] = None
        self.on_worker_failed: Optional[Callable] = None
        self.on_status_update: Optional[Callable] = None

    async def trigger_job_started(self, job_id: str):
        if self.on_job_started:
            await self.on_job_started(job_id)

    async def trigger_job_completed(self, result: ExecutionResult):
        if self.on_job_completed:
            await self.on_job_completed(result)

    async def trigger_worker_started(self, worker_id: int, job_id: str):
        if self.on_worker_started:
            await self.on_worker_started(worker_id, job_id)

    async def trigger_worker_completed(self, worker_result: WorkerResult):
        if self.on_worker_completed:
            await self.on_worker_completed(worker_result)

    async def trigger_worker_failed(self, worker_id: int, error: str):
        if self.on_worker_failed:
            await self.on_worker_failed(worker_id, error)

    async def trigger_status_update(self, job_id: str, status: str, message: str):
        if self.on_status_update:
            await self.on_status_update(job_id, status, message)


class ExecutionService:
    """
    Shared execution service for minting operations.
    Used by both CLI and web platforms.
    """

    def __init__(self):
        self.active_jobs: Dict[str, asyncio.Task] = {}

    async def execute_mint_job(
        self,
        job_id: str,
        config: MintConfiguration,
        workers: List[WorkerConfig],
        callbacks: Optional[ExecutionCallbacks] = None
    ) -> ExecutionResult:
        """
        Execute a minting job with multiple workers.

        Args:
            job_id: Unique identifier for this job
            config: Minting configuration
            workers: List of worker configurations
            callbacks: Optional callbacks for events

        Returns:
            ExecutionResult with job outcome
        """
        import time
        start_time = time.time()

        if callbacks is None:
            callbacks = ExecutionCallbacks()

        # Validate configuration
        try:
            self._validate_config(config)
        except ValidationError as e:
            return ExecutionResult(
                job_id=job_id,
                status=JobStatus.FAILED,
                workers=[],
                successful_mints=0,
                failed_mints=len(workers),
                total_gas_cost=0.0,
                duration_seconds=0.0
            )

        await callbacks.trigger_job_started(job_id)

        # Execute workers
        worker_results = []
        tasks = []

        for idx, worker_config in enumerate(workers):
            worker_id = worker_config.worker_id or (idx + 1)
            task = asyncio.create_task(
                self._execute_worker(
                    job_id=job_id,
                    worker_id=worker_id,
                    worker_config=worker_config,
                    mint_config=config,
                    callbacks=callbacks
                )
            )
            tasks.append(task)

        # Wait for all workers to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        successful_mints = 0
        failed_mints = 0
        total_gas_cost = 0.0

        for result in results:
            if isinstance(result, WorkerResult):
                worker_results.append(result)
                if result.status == "success":
                    successful_mints += 1
                    if result.gas_used:
                        total_gas_cost += result.gas_used
                else:
                    failed_mints += 1

        duration = time.time() - start_time

        execution_result = ExecutionResult(
            job_id=job_id,
            status=JobStatus.COMPLETED if successful_mints > 0 else JobStatus.FAILED,
            workers=worker_results,
            successful_mints=successful_mints,
            failed_mints=failed_mints,
            total_gas_cost=total_gas_cost,
            duration_seconds=duration
        )

        await callbacks.trigger_job_completed(execution_result)

        return execution_result

    async def _execute_worker(
        self,
        job_id: str,
        worker_id: int,
        worker_config: WorkerConfig,
        mint_config: MintConfiguration,
        callbacks: ExecutionCallbacks
    ) -> WorkerResult:
        """Execute a single worker"""
        await callbacks.trigger_worker_started(worker_id, job_id)

        try:
            # Import ExecutionUnit here to avoid circular imports
            from src.engine.execution import ExecutionUnit
            from src.config.settings import ConfigurationManager

            # Create a configuration object compatible with ExecutionUnit
            # This is a bridge between the service layer and existing implementation
            cfg = self._create_config_from_mint_config(mint_config)

            # Create and run execution unit
            unit = ExecutionUnit(worker_config.private_key, worker_id, cfg)
            await unit.run_protocol()

            # Success
            result = WorkerResult(
                worker_id=worker_id,
                status="success",
                tx_hash=None,  # Would be populated by ExecutionUnit
                error_message=None
            )

            await callbacks.trigger_worker_completed(result)
            return result

        except Exception as e:
            # Failure
            error_msg = str(e)[:200]
            await callbacks.trigger_worker_failed(worker_id, error_msg)

            return WorkerResult(
                worker_id=worker_id,
                status="failed",
                error_message=error_msg
            )

    def _validate_config(self, config: MintConfiguration):
        """Validate mint configuration"""
        validator.validate_ethereum_address(config.nft_contract)

        if config.recipient_address:
            validator.validate_ethereum_address(config.recipient_address)

        if config.mint_mode == "DIRECT":
            validator.validate_mint_function_name(config.mint_func_name)

        validator.validate_quantity(config.mint_quantity)

    def _create_config_from_mint_config(self, mint_config: MintConfiguration):
        """
        Create ConfigurationManager-compatible object from MintConfiguration.
        This is a temporary bridge until full refactor.
        """
        class BridgeConfig:
            def __init__(self, mc: MintConfiguration):
                self.rpc_ticker = mc.network
                self.target_nft = mc.nft_contract
                self.qty = mc.mint_quantity
                self.mint_mode = mc.mint_mode
                self.mint_func_name = mc.mint_func_name
                self.recipient = mc.recipient_address
                self.presign_enabled = mc.presign_enabled
                self.transfer_enabled = mc.auto_transfer_enabled
                self.sweep_enabled = mc.auto_sweep_enabled
                self.gas_gwei = mc.gas_gwei
                self.max_gas_limit = mc.max_gas_limit

                # Defaults from existing system
                self.sea_addr = "0x00005EA00Ac477B1030CE78506496e8C2dE24bf5"
                self.multi_addr = "0x0000419B4B6132e05DfBd89F65B165DFD6fA126F"
                self.max_threads = 5
                self.delay_range = (1.0, 3.0)
                self.min_sweep_eth = 0.005
                self.fund_enabled = False
                self.discord_enabled = False
                self.accountant_enabled = False
                self.verifier_enabled = False
                self.force_start = False
                self.use_proxies = False
                self.proxies = []
                self.presign_gas_mult = 2.0
                self.presign_gas_limit = 300000

        return BridgeConfig(mint_config)

    async def cancel_job(self, job_id: str):
        """Cancel a running job"""
        if job_id in self.active_jobs:
            task = self.active_jobs[job_id]
            task.cancel()
            del self.active_jobs[job_id]

    async def get_job_status(self, job_id: str) -> Optional[str]:
        """Get status of a running job"""
        if job_id in self.active_jobs:
            task = self.active_jobs[job_id]
            if task.done():
                return "completed"
            return "running"
        return None


# Global instance
execution_service = ExecutionService()

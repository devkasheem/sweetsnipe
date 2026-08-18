"""
Updated job queue using the shared execution service.
Implements concurrent job processing with proper isolation.
"""
import asyncio
import json
from datetime import datetime
from typing import Dict, Set
from fastapi import WebSocket
from sqlalchemy.orm import Session

from backend.database import SessionLocal, Job, Worker
from backend.config import decrypt_key
from src.core.execution_service import (
    ExecutionService,
    MintConfiguration,
    WorkerConfig,
    ExecutionCallbacks,
    JobStatus
)


class ImprovedJobQueue:
    """
    Improved job queue with concurrent processing capability.
    """

    def __init__(self, max_concurrent_jobs: int = 5):
        self.execution_service = ExecutionService()
        self.max_concurrent_jobs = max_concurrent_jobs
        self.active_jobs: Dict[str, Dict] = {}
        self.websocket_connections: Dict[str, Set[WebSocket]] = {}
        self.running = False
        self._worker_task = None
        self._job_semaphore = asyncio.Semaphore(max_concurrent_jobs)

    async def start(self):
        """Start the job queue processor"""
        if self.running:
            return
        self.running = True
        self._worker_task = asyncio.create_task(self._process_queue())

    async def stop(self):
        """Stop the job queue processor"""
        self.running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

    def add_job(self, job_id: str):
        """Add a job to the queue"""
        self.active_jobs[job_id] = {
            "status": "queued",
            "task": None,
            "started_at": None
        }

    async def _process_queue(self):
        """Process queued jobs with concurrency control"""
        while self.running:
            db = SessionLocal()
            try:
                # Get queued jobs
                pending_jobs = db.query(Job).filter(Job.status == "queued").all()

                for job in pending_jobs:
                    if job.id not in self.active_jobs:
                        self.add_job(job.id)

                    job_info = self.active_jobs.get(job.id)
                    if job_info and job_info.get("status") == "queued":
                        # Try to acquire semaphore (non-blocking)
                        if self._job_semaphore.locked():
                            # Max concurrent jobs reached, skip for now
                            continue

                        # Mark as running
                        job_info["status"] = "running"
                        job.started_at = datetime.utcnow()
                        job.status = "running"
                        db.commit()

                        # Start execution task
                        task = asyncio.create_task(
                            self._execute_job_with_semaphore(job.id)
                        )
                        job_info["task"] = task

            except Exception as e:
                print(f"Queue processing error: {e}")
            finally:
                db.close()

            await asyncio.sleep(1)

    async def _execute_job_with_semaphore(self, job_id: str):
        """Execute job while holding semaphore"""
        async with self._job_semaphore:
            await self._execute_job(job_id)

    async def _execute_job(self, job_id: str):
        """Execute a single job using execution service"""
        db = SessionLocal()
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                return

            workers = db.query(Worker).filter(Worker.job_id == job_id).all()

            # Create mint configuration
            mint_config = MintConfiguration(
                network=job.network,
                nft_contract=job.nft_contract,
                mint_quantity=job.mint_quantity,
                mint_mode=job.mint_mode,
                mint_func_name=job.mint_func_name or "mint",
                recipient_address=job.recipient_address,
                presign_enabled=job.presign_enabled,
                auto_transfer_enabled=job.auto_transfer_enabled,
                auto_sweep_enabled=job.auto_sweep_enabled
            )

            # Create worker configurations
            worker_configs = []
            for w in workers:
                pk = decrypt_key(w.encrypted_private_key)
                worker_configs.append(WorkerConfig(
                    private_key=pk,
                    proxy_url=w.proxy_url
                ))

            # Create callbacks
            callbacks = self._create_callbacks(job_id, db)

            # Execute job
            result = await self.execution_service.execute_mint_job(
                job_id=job_id,
                config=mint_config,
                workers=worker_configs,
                callbacks=callbacks
            )

            # Update job status
            job.status = result.status.value
            job.successful_mints = result.successful_mints
            job.failed_mints = result.failed_mints
            job.completed_at = datetime.utcnow()
            db.commit()

            # Update active jobs
            if job_id in self.active_jobs:
                self.active_jobs[job_id]["status"] = "completed"

            self._broadcast_job_update(job_id)

        except Exception as e:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = "failed"
                db.commit()
            self._broadcast_job_update(job_id)
            print(f"Job execution error: {e}")
        finally:
            db.close()

    def _create_callbacks(self, job_id: str, db: Session) -> ExecutionCallbacks:
        """Create callbacks for job execution"""
        callbacks = ExecutionCallbacks()

        async def on_worker_completed(worker_result):
            # Update worker in database
            worker = db.query(Worker).filter(
                Worker.job_id == job_id,
                Worker.id == worker_result.worker_id
            ).first()

            if worker:
                worker.status = worker_result.status
                worker.tx_hash = worker_result.tx_hash
                worker.error_message = worker_result.error_message
                db.commit()
                self._broadcast_job_update(job_id)

        callbacks.on_worker_completed = on_worker_completed
        return callbacks

    async def register(self, job_id: str, websocket: WebSocket):
        """Register WebSocket for job updates"""
        if job_id not in self.websocket_connections:
            self.websocket_connections[job_id] = set()
        self.websocket_connections[job_id].add(websocket)

    async def unregister(self, job_id: str, websocket: WebSocket):
        """Unregister WebSocket"""
        if job_id in self.websocket_connections:
            self.websocket_connections[job_id].discard(websocket)

    def _broadcast_job_update(self, job_id: str):
        """Broadcast job update to WebSocket clients"""
        if job_id not in self.websocket_connections:
            return

        db = SessionLocal()
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            workers = db.query(Worker).filter(Worker.job_id == job_id).all()

            data = {
                "type": "job_update",
                "job": {
                    "id": job.id,
                    "status": job.status,
                    "successful_mints": job.successful_mints,
                    "failed_mints": job.failed_mints,
                    "total_wallets": job.total_wallets
                },
                "workers": [
                    {
                        "id": w.id,
                        "status": w.status,
                        "balance": w.balance,
                        "tx_hash": w.tx_hash,
                        "error_message": w.error_message
                    }
                    for w in workers
                ]
            }

            message = json.dumps(data)
            for ws in list(self.websocket_connections[job_id]):
                asyncio.create_task(ws.send_text(message))
        finally:
            db.close()


# Create improved job queue instance
improved_job_queue = ImprovedJobQueue(max_concurrent_jobs=5)

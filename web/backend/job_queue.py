import asyncio
import json
import random
import time
from datetime import datetime
from typing import Dict, Set
from fastapi import WebSocket
from sqlalchemy.orm import Session
from backend.database import SessionLocal, Job, Worker
from backend.config import decrypt_key, settings
from src.config.settings import NETWORKS, ContractSpecs
from src.engine.execution import ExecutionUnit
from src.ui.logger import Logger

class JobQueue:
    def __init__(self):
        self.active_jobs: Dict[str, Dict] = {}
        self.websocket_connections: Dict[str, Set[WebSocket]] = {}
        self.running = False
        self._worker_task = None

    async def start(self):
        if self.running:
            return
        self.running = True
        self._worker_task = asyncio.create_task(self._process_queue())

    async def stop(self):
        self.running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

    def add_job(self, job_id: str):
        self.active_jobs[job_id] = {
            "status": "queued",
            "task": None,
            "started_at": None
        }
        asyncio.create_task(self._process_queue())

    async def _process_queue(self):
        while self.running:
            db = SessionLocal()
            try:
                pending_jobs = db.query(Job).filter(Job.status == "queued").all()
                for job in pending_jobs:
                    if job.id not in self.active_jobs:
                        self.add_job(job.id)
                    
                    job_info = self.active_jobs.get(job.id)
                    if job_info and job_info.get("status") == "queued":
                        job_info["status"] = "running"
                        job.started_at = datetime.utcnow()
                        job.status = "running"
                        db.commit()
                        
                        task = asyncio.create_task(self._execute_job(job.id))
                        job_info["task"] = task
            except Exception as e:
                print(f"Queue error: {e}")
            finally:
                db.close()
            
            await asyncio.sleep(1)

    async def _execute_job(self, job_id: str):
        db = SessionLocal()
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                return
            
            workers = db.query(Worker).filter(Worker.job_id == job_id).all()
            
            class WebConfig:
                def __init__(self, job, workers):
                    self.rpc_ticker = job.network
                    self.sea_addr = "0x00005EA00Ac477B1030CE78506496e8C2dE24bf5"
                    self.multi_addr = "0x0000419B4B6132e05DfBd89F65B165DFD6fA126F"
                    self.target_nft = job.nft_contract
                    self.qty = job.mint_quantity
                    self.max_threads = 5
                    self.gas_gwei = ""
                    self.max_gas_limit = 100
                    self.delay_range = (1.0, 3.0)
                    self.transfer_enabled = job.auto_transfer_enabled
                    self.recipient = job.recipient_address
                    self.sweep_enabled = job.auto_sweep_enabled
                    self.min_sweep_eth = 0.005
                    self.fund_enabled = False
                    self.master_pk = ""
                    self.min_worker_balance = 0.005
                    self.funding_amount = 0.01
                    self.webhook_url = ""
                    self.discord_enabled = False
                    self.force_start = False
                    self.use_proxies = False
                    self.proxies = []
                    self.mint_mode = job.mint_mode
                    self.mint_func_name = job.mint_func_name or "mint"
                    self.accountant_enabled = False
                    self.verifier_enabled = False
                    self.explorer_api_key = ""
                    self.presign_enabled = job.presign_enabled
                    self.presign_gas_mult = 2.0
                    self.presign_gas_limit = 300000
            
            config = WebConfig(job, workers)
            semaphore = asyncio.Semaphore(config.max_threads)
            
            async def run_worker(worker_data):
                async with semaphore:
                    try:
                        pk = decrypt_key(worker_data.encrypted_private_key)
                        unit = ExecutionUnit(pk, 0, config)
                        await unit.run_protocol()
                        
                        worker_data.status = "success"
                        worker_data.balance = "0"
                        db.commit()
                        self._broadcast_job_update(job_id)
                    except Exception as e:
                        worker_data.status = "failed"
                        worker_data.error_message = str(e)[:200]
                        db.commit()
                        self._broadcast_job_update(job_id)
            
            tasks = []
            for w in workers:
                tasks.append(run_worker(w))
            
            await asyncio.gather(*tasks, return_exceptions=True)
            
            job.status = "completed"
            job.completed_at = datetime.utcnow()
            db.commit()
            
            if job_id in self.active_jobs:
                self.active_jobs[job_id]["status"] = "completed"
            
            self._broadcast_job_update(job_id)
            
        except Exception as e:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = "failed"
                db.commit()
            self._broadcast_job_update(job_id)
        finally:
            db.close()

    async def register(self, job_id: str, websocket: WebSocket):
        if job_id not in self.websocket_connections:
            self.websocket_connections[job_id] = set()
        self.websocket_connections[job_id].add(websocket)

    async def unregister(self, job_id: str, websocket: WebSocket):
        if job_id in self.websocket_connections:
            self.websocket_connections[job_id].discard(websocket)

    def _broadcast_job_update(self, job_id: str):
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

job_queue = JobQueue()

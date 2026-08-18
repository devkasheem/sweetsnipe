"""
Structured logging service for production observability.
Outputs JSON logs for easy parsing by log aggregation systems (ELK, Datadog, etc.)
"""
import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path


class StructuredLogger:
    """
    Structured JSON logger for production environments.
    Provides consistent log format across all services.
    """

    def __init__(
        self,
        service_name: str,
        log_level: str = "INFO",
        log_file: Optional[str] = None,
        enable_console: bool = True
    ):
        self.service_name = service_name
        self.logger = logging.getLogger(service_name)
        self.logger.setLevel(getattr(logging, log_level.upper()))
        self.logger.handlers = []  # Clear existing handlers

        # Console handler (JSON)
        if enable_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(self._json_formatter())
            self.logger.addHandler(console_handler)

        # File handler (JSON)
        if log_file:
            Path(log_file).parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(self._json_formatter())
            self.logger.addHandler(file_handler)

    def _json_formatter(self):
        """Create a JSON formatter"""
        class JsonFormatter(logging.Formatter):
            def format(self, record):
                log_data = {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "level": record.levelname,
                    "service": record.name,
                    "message": record.getMessage(),
                    "module": record.module,
                    "function": record.funcName,
                    "line": record.lineno,
                }

                # Add extra fields if present
                if hasattr(record, 'extra_fields'):
                    log_data.update(record.extra_fields)

                # Add exception info if present
                if record.exc_info:
                    log_data["exception"] = self.formatException(record.exc_info)

                return json.dumps(log_data)

        return JsonFormatter()

    def _log(self, level: str, message: str, **kwargs):
        """Internal log method with extra fields"""
        extra = {'extra_fields': kwargs}
        getattr(self.logger, level.lower())(message, extra=extra)

    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self._log("DEBUG", message, **kwargs)

    def info(self, message: str, **kwargs):
        """Log info message"""
        self._log("INFO", message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self._log("WARNING", message, **kwargs)

    def error(self, message: str, **kwargs):
        """Log error message"""
        self._log("ERROR", message, **kwargs)

    def critical(self, message: str, **kwargs):
        """Log critical message"""
        self._log("CRITICAL", message, **kwargs)

    def log_execution(
        self,
        worker_id: int,
        job_id: str,
        event: str,
        **kwargs
    ):
        """Log execution-specific event"""
        self.info(
            f"Worker {worker_id} execution event",
            worker_id=worker_id,
            job_id=job_id,
            event=event,
            **kwargs
        )

    def log_transaction(
        self,
        tx_hash: str,
        network: str,
        status: str,
        **kwargs
    ):
        """Log blockchain transaction"""
        self.info(
            f"Transaction {status}",
            tx_hash=tx_hash,
            network=network,
            status=status,
            **kwargs
        )

    def log_api_request(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        **kwargs
    ):
        """Log API request"""
        self.info(
            f"{method} {path} - {status_code}",
            method=method,
            path=path,
            status_code=status_code,
            duration_ms=duration_ms,
            **kwargs
        )

    def log_job_status(
        self,
        job_id: str,
        status: str,
        user_id: str,
        **kwargs
    ):
        """Log job status change"""
        self.info(
            f"Job {job_id} status: {status}",
            job_id=job_id,
            status=status,
            user_id=user_id,
            **kwargs
        )


# Global logger instances
def get_logger(service_name: str, log_level: str = "INFO") -> StructuredLogger:
    """Get or create a structured logger for a service"""
    return StructuredLogger(
        service_name=service_name,
        log_level=log_level,
        log_file=f"logs/{service_name}.json",
        enable_console=True
    )


# Pre-configured loggers for different services
execution_logger = get_logger("execution_engine")
api_logger = get_logger("api")
payment_logger = get_logger("payment_service")
job_queue_logger = get_logger("job_queue")

"""
Circuit Breaker pattern implementation to prevent infinite retries.
"""
import asyncio
import time
from typing import Callable, Any, Optional
from enum import Enum
from src.shared.constants import MAX_RETRY_ATTEMPTS, MAX_EXECUTION_TIME


class CircuitState(Enum):
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Failure threshold exceeded, reject calls
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker to prevent infinite retry loops.
    Tracks failures and opens circuit after threshold.
    """

    def __init__(
        self,
        failure_threshold: int = 10,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = CircuitState.CLOSED

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.failure_count = 0
            else:
                raise Exception("Circuit breaker is OPEN - too many failures")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e

    async def call_async(self, func: Callable, *args, **kwargs) -> Any:
        """Execute async function with circuit breaker protection."""
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.failure_count = 0
            else:
                raise Exception("Circuit breaker is OPEN - too many failures")

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e

    def _on_success(self):
        """Reset failure count on success."""
        self.failure_count = 0
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED

    def _on_failure(self):
        """Increment failure count and open circuit if threshold exceeded."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN

    def reset(self):
        """Manually reset the circuit breaker."""
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.last_failure_time = None


class ExecutionTimeoutError(Exception):
    """Raised when execution exceeds maximum allowed time."""
    pass


async def with_retry_and_timeout(
    func: Callable,
    *args,
    max_attempts: int = MAX_RETRY_ATTEMPTS,
    max_duration: float = MAX_EXECUTION_TIME,
    retry_delay: float = 2.0,
    exponential_backoff: bool = True,
    **kwargs
) -> Any:
    """
    Execute function with retry logic and maximum execution time.

    Args:
        func: Async function to execute
        max_attempts: Maximum retry attempts
        max_duration: Maximum total execution time in seconds
        retry_delay: Base delay between retries
        exponential_backoff: Use exponential backoff for retries

    Raises:
        ExecutionTimeoutError: If execution exceeds max_duration
        Exception: If all retries exhausted
    """
    start_time = time.time()
    attempt = 0

    while attempt < max_attempts:
        # Check if we've exceeded maximum execution time
        elapsed = time.time() - start_time
        if elapsed >= max_duration:
            raise ExecutionTimeoutError(
                f"Execution exceeded maximum time of {max_duration}s (elapsed: {elapsed:.1f}s)"
            )

        try:
            return await func(*args, **kwargs)
        except Exception as e:
            attempt += 1

            if attempt >= max_attempts:
                raise Exception(f"Max attempts ({max_attempts}) exceeded. Last error: {e}")

            # Calculate delay with exponential backoff
            if exponential_backoff:
                delay = min(retry_delay * (2 ** (attempt - 1)), 60)  # Cap at 60s
            else:
                delay = retry_delay

            # Don't sleep if we'd exceed max duration
            if time.time() - start_time + delay < max_duration:
                await asyncio.sleep(delay)
            else:
                raise ExecutionTimeoutError(
                    f"Cannot retry - would exceed maximum execution time"
                )

"""
Circuit Breaker Pattern Implementation
Prevents cascade failures when external services are unavailable
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from enum import Enum
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class CircuitBreakerState(Enum):
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Circuit is open, failing fast
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreakerOpenException(Exception):
    """Exception raised when circuit breaker is open"""

    pass


class CircuitBreaker:
    """Circuit breaker implementation with async support"""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: Exception = Exception,
        success_threshold: int = 3,
        timeout: float = 10.0,
        name: str = "default",
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.success_threshold = success_threshold
        self.timeout = timeout
        self.name = name

        # State management
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None

        # Locks for thread safety
        self._lock = asyncio.Lock()

    async def _should_attempt_reset(self) -> bool:
        """Check if we should attempt to reset the circuit breaker"""
        if self.last_failure_time is None:
            return False
        return time.time() - self.last_failure_time >= self.recovery_timeout

    async def _record_success(self):
        """Record a successful call"""
        async with self._lock:
            self.success_count += 1
            if (
                self.state == CircuitBreakerState.HALF_OPEN
                and self.success_count >= self.success_threshold
            ):
                self._reset()
            elif self.state == CircuitBreakerState.CLOSED:
                self.failure_count = 0

    async def _record_failure(self):
        """Record a failed call"""
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.failure_count >= self.failure_threshold:
                self.state = CircuitBreakerState.OPEN
                logger.warning(
                    f"Circuit breaker '{self.name}' opened due to {self.failure_count} failures"
                )

    def _reset(self):
        """Reset the circuit breaker to closed state"""
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        logger.info(f"Circuit breaker '{self.name}' reset to closed state")

    def _can_attempt_call(self) -> bool:
        """Check if a call can be attempted"""
        if self.state == CircuitBreakerState.CLOSED:
            return True
        elif self.state == CircuitBreakerState.OPEN:
            if asyncio.run(self._should_attempt_reset()):
                self.state = CircuitBreakerState.HALF_OPEN
                self.success_count = 0
                logger.info(f"Circuit breaker '{self.name}' attempting reset")
                return True
            return False
        else:  # HALF_OPEN
            return True

    @asynccontextmanager
    async def call_context(self):
        """Context manager for circuit breaker protected calls"""
        if not self._can_attempt_call():
            raise CircuitBreakerOpenException(f"Circuit breaker '{self.name}' is OPEN")

        try:
            yield
            await self._record_success()
        except self.expected_exception as e:
            await self._record_failure()
            raise
        except Exception as e:
            # For unexpected exceptions, don't count as circuit breaker failures
            raise

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute a function with circuit breaker protection"""
        async with self.call_context():
            # Add timeout to the call
            try:
                if asyncio.iscoroutinefunction(func):
                    return await asyncio.wait_for(
                        func(*args, **kwargs), timeout=self.timeout
                    )
                else:
                    return await asyncio.get_event_loop().run_in_executor(
                        None, lambda: func(*args, **kwargs)
                    )
            except asyncio.TimeoutError:
                await self._record_failure()
                raise Exception(
                    f"Call to {func.__name__} timed out after {self.timeout}s"
                )

    def get_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
        }


# Global circuit breaker instances for different services
epa_api_circuit_breaker = CircuitBreaker(
    name="epa_api",
    failure_threshold=3,
    recovery_timeout=30.0,  # 30 seconds
    timeout=15.0,  # 15 second timeout
)

sec_api_circuit_breaker = CircuitBreaker(
    name="sec_api",
    failure_threshold=5,
    recovery_timeout=60.0,  # 1 minute
    timeout=10.0,  # 10 second timeout
)

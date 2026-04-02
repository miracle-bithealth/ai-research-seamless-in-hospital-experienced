import asyncio
import logging
import time
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Generic circuit breaker for external API calls.

    States:
      CLOSED   - normal operation, failures counted
      OPEN     - calls rejected, fallback used
      HALF_OPEN - single test call allowed to probe recovery
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
        fallback: Optional[Callable] = None,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.fallback = fallback

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            elapsed = time.time() - self._last_failure_time
            if elapsed >= self.recovery_timeout:
                return CircuitState.HALF_OPEN
        return self._state

    async def call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        async with self._lock:
            current_state = self.state

            if current_state == CircuitState.OPEN:
                logger.warning("Circuit %s is OPEN, using fallback", self.name)
                if self.fallback:
                    return await self._execute(self.fallback, *args, **kwargs)
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is open"
                )

        try:
            result = await self._execute(func, *args, **kwargs)
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure()
            if self.fallback:
                logger.warning(
                    "Circuit %s: call failed (%s), using fallback",
                    self.name, e,
                )
                return await self._execute(self.fallback, *args, **kwargs)
            raise

    async def _execute(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        return func(*args, **kwargs)

    async def _on_success(self) -> None:
        async with self._lock:
            self._failure_count = 0
            if self._state != CircuitState.CLOSED:
                logger.info("Circuit %s: recovered, state -> CLOSED", self.name)
                self._state = CircuitState.CLOSED

    async def _on_failure(self) -> None:
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    "Circuit %s: threshold reached (%d), state -> OPEN",
                    self.name, self._failure_count,
                )

    def reset(self) -> None:
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0


class CircuitBreakerOpenError(Exception):
    pass

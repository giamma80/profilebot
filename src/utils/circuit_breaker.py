"""Circuit breaker state machine for ingestion sources."""

from __future__ import annotations

import logging
import time
from enum import StrEnum

logger = logging.getLogger(__name__)


class CircuitState(StrEnum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpen(Exception):
    """Raised when the circuit breaker is open and calls are rejected."""

    def __init__(self, source_type: str, reset_at: float) -> None:
        self.source_type = source_type
        self.reset_at = reset_at
        remaining = max(0, reset_at - time.time())
        super().__init__(f"Circuit breaker OPEN for '{source_type}', retry in {remaining:.1f}s")


class CircuitBreaker:
    """Simple circuit breaker state machine.

    States:
        - CLOSED: Normal operation, calls pass through. Failures increment counter.
        - OPEN: Calls rejected immediately. After ``reset_timeout_s`` → HALF_OPEN.
        - HALF_OPEN: One trial call allowed. Success → CLOSED, failure → OPEN.

    Args:
        source_type: Label for logging and error messages.
        failure_threshold: Consecutive failures to trip CLOSED → OPEN.
        reset_timeout_s: Seconds before OPEN → HALF_OPEN.
    """

    def __init__(
        self,
        source_type: str,
        *,
        failure_threshold: int = 5,
        reset_timeout_s: float = 60.0,
    ) -> None:
        self.source_type = source_type
        self.failure_threshold = failure_threshold
        self.reset_timeout_s = reset_timeout_s

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._opened_at: float = 0.0

    @property
    def state(self) -> CircuitState:
        """Current circuit state (may transition OPEN → HALF_OPEN on access)."""
        if self._state == CircuitState.OPEN:
            if time.time() - self._opened_at >= self.reset_timeout_s:
                self._state = CircuitState.HALF_OPEN
                logger.info(
                    "circuit_breaker_half_open source_type=%s",
                    self.source_type,
                )
        return self._state

    def allow_request(self) -> bool:
        """Check whether a request is allowed through the breaker."""
        current = self.state
        if current == CircuitState.CLOSED:
            return True
        if current == CircuitState.HALF_OPEN:
            return True
        return False

    def before_call(self) -> None:
        """Call before executing the protected operation.

        Raises:
            CircuitBreakerOpen: If the circuit is OPEN.
        """
        if not self.allow_request():
            raise CircuitBreakerOpen(
                self.source_type,
                self._opened_at + self.reset_timeout_s,
            )

    def record_success(self) -> None:
        """Record a successful call — reset to CLOSED."""
        if self._state != CircuitState.CLOSED:
            logger.info(
                "circuit_breaker_closed source_type=%s (recovered)",
                self.source_type,
            )
        self._state = CircuitState.CLOSED
        self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed call — increment counter, possibly trip to OPEN."""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            # Trial call failed — back to OPEN
            self._trip_open()
            return

        if self._failure_count >= self.failure_threshold:
            self._trip_open()

    def _trip_open(self) -> None:
        self._state = CircuitState.OPEN
        self._opened_at = time.time()
        logger.warning(
            "circuit_breaker_open source_type=%s failures=%d",
            self.source_type,
            self._failure_count,
        )

    def reset(self) -> None:
        """Force-reset the breaker to CLOSED (for testing/admin)."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._opened_at = 0.0
        self._last_failure_time = 0.0

    def to_dict(self) -> dict[str, object]:
        """Serialize current state for API/monitoring."""
        return {
            "source_type": self.source_type,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "reset_timeout_s": self.reset_timeout_s,
        }


__all__ = [
    "CircuitBreaker",
    "CircuitBreakerOpen",
    "CircuitState",
]

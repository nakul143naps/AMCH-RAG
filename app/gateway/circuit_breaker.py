"""Circuit breaker for protecting upstream model providers during outages or rate-limit cascades."""

import logging
import time
from enum import Enum

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Enumeration of circuit breaker operational states."""

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """Stateful circuit breaker tracking provider failures and cooldowns.

    States:
    - CLOSED: Normal operation. Requests pass through.
    - OPEN: Provider has failed >= failure_threshold times consecutively. Requests fail fast.
    - HALF_OPEN: Cooldown has passed. A trial request is permitted. If successful, resets to CLOSED.
    """

    def __init__(
        self,
        provider_name: str,
        failure_threshold: int = 3,
        cooldown_seconds: float = 30.0,
    ) -> None:
        self.provider_name = provider_name
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds

        self.consecutive_failures: int = 0
        self.state: CircuitState = CircuitState.CLOSED
        self.last_failure_time: float = 0.0

    def can_execute(self) -> bool:
        """Check if request to provider should be permitted."""
        now = time.time()
        if self.state == "CLOSED":
            return True

        if self.state == "OPEN":
            if now - self.last_failure_time >= self.cooldown_seconds:
                logger.info(
                    f"CircuitBreaker [{self.provider_name}]: Cooldown of {self.cooldown_seconds}s expired -> transitioning OPEN to HALF_OPEN trial"
                )
                self.state = "HALF_OPEN"
                return True
            return False

        if self.state == "HALF_OPEN":
            # Allow single trial request
            return True

        return True

    def record_success(self) -> None:
        """Record successful invocation, resetting circuit to CLOSED."""
        if self.state in ("OPEN", "HALF_OPEN"):
            logger.info(
                f"CircuitBreaker [{self.provider_name}]: Trial succeeded -> resetting from {self.state} to CLOSED"
            )
        self.state = "CLOSED"
        self.consecutive_failures = 0

    def record_failure(self, error: Exception | str) -> None:
        """Record provider error. If consecutive failures exceed threshold, trips to OPEN."""
        self.consecutive_failures += 1
        self.last_failure_time = time.time()

        if self.consecutive_failures >= self.failure_threshold:
            if self.state != "OPEN":
                logger.warning(
                    f"CircuitBreaker [{self.provider_name}]: {self.consecutive_failures} consecutive failures (last error: {error}) -> tripping circuit to OPEN for {self.cooldown_seconds}s cooldown"
                )
            self.state = "OPEN"
        else:
            logger.warning(
                f"CircuitBreaker [{self.provider_name}]: Failure {self.consecutive_failures}/{self.failure_threshold} recorded"
            )

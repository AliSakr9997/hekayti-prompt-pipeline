"""Bounded retry policy and transport-error classification."""

from dataclasses import dataclass
from enum import Enum
import random
from typing import Callable, TypeVar

T = TypeVar("T")


class RetryClass(str, Enum):
    TRANSIENT = "transient"
    RATE_LIMIT = "rate_limit"
    PERMANENT = "permanent"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_seconds: float = 0.5
    max_delay_seconds: float = 8.0
    jitter_seconds: float = 0.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1 or self.base_delay_seconds < 0 or self.max_delay_seconds < 0:
            raise ValueError("retry limits must be non-negative and max_attempts must be positive")


def classify_error(error: BaseException) -> RetryClass:
    status = getattr(error, "status_code", None)
    if status == 429:
        return RetryClass.RATE_LIMIT
    if isinstance(status, int) and status >= 500:
        return RetryClass.TRANSIENT
    if isinstance(error, (TimeoutError, ConnectionError)):
        return RetryClass.TRANSIENT
    if isinstance(status, int) and 400 <= status < 500:
        return RetryClass.PERMANENT
    return RetryClass.UNKNOWN


def retry_call(fn: Callable[[], T], policy: RetryPolicy = RetryPolicy(),
               *, sleep: Callable[[float], None],
               classify: Callable[[BaseException], RetryClass] = classify_error) -> T:
    last: BaseException | None = None
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return fn()
        except Exception as error:
            last = error
            category = classify(error)
            if category not in (RetryClass.TRANSIENT, RetryClass.RATE_LIMIT) or attempt == policy.max_attempts:
                raise
            delay = min(policy.max_delay_seconds, policy.base_delay_seconds * (2 ** (attempt - 1)))
            if policy.jitter_seconds:
                delay += random.uniform(0, policy.jitter_seconds)
            sleep(delay)
    raise last  # pragma: no cover

"""QA outcomes and stable failure categories."""

from dataclasses import dataclass
from enum import Enum


class QAFailureCategory(str, Enum):
    IDENTITY = "identity"
    TECHNICAL = "technical"
    COMPOSITION = "composition"
    SAFETY = "safety"
    PROVIDER = "provider"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class QAResult:
    passed: bool
    score: float
    failures: tuple[QAFailureCategory, ...] = ()
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not 0 <= self.score <= 1:
            raise ValueError("score must be between 0 and 1")
        if self.passed and self.failures:
            raise ValueError("a passing result cannot contain failures")


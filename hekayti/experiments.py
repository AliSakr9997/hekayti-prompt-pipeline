"""Experiment runner interface that deliberately does not make provider calls."""

from dataclasses import dataclass
from typing import Callable, Iterable, Protocol

from .metrics import RunMetric
from .models import Strategy
from .providers import ImageRequest


class StrategyExecutor(Protocol):
    def __call__(self, request: ImageRequest) -> RunMetric: ...


@dataclass(frozen=True)
class StrategyResult:
    strategy: Strategy
    metric: RunMetric


class ExperimentRunner:
    """Compare strategies using an injected executor; no network is performed."""

    def __init__(self, executor: StrategyExecutor) -> None:
        self.executor = executor

    def compare(self, request_factory: Callable[[Strategy], ImageRequest],
                strategies: Iterable[Strategy] = (Strategy.SHEET, Strategy.PHOTOS, Strategy.HYBRID)
                ) -> tuple[StrategyResult, ...]:
        return tuple(
            StrategyResult(strategy, self.executor(request_factory(strategy)))
            for strategy in strategies
        )


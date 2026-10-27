"""Cost and latency aggregation for provider-independent experiment reporting."""

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class RunMetric:
    strategy: str
    latency_ms: float
    cost: float
    qa_score: float = 0.0
    passed: bool = False


@dataclass(frozen=True)
class AggregateMetric:
    runs: int
    total_cost: float
    average_cost: float
    average_latency_ms: float
    pass_rate: float
    average_qa_score: float


def aggregate_metrics(metrics: Iterable[RunMetric]) -> AggregateMetric:
    values = list(metrics)
    if not values:
        return AggregateMetric(0, 0.0, 0.0, 0.0, 0.0, 0.0)
    count = len(values)
    return AggregateMetric(
        runs=count,
        total_cost=sum(item.cost for item in values),
        average_cost=sum(item.cost for item in values) / count,
        average_latency_ms=sum(item.latency_ms for item in values) / count,
        pass_rate=sum(item.passed for item in values) / count,
        average_qa_score=sum(item.qa_score for item in values) / count,
    )


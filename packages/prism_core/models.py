from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


Horizon = Literal["10D", "30D", "90D"]


@dataclass(frozen=True)
class Bar:
    symbol: str
    timestamp: datetime
    available_at: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    source: str

    def assert_available(self, cutoff: datetime) -> None:
        if self.available_at > cutoff:
            raise ValueError(
                f"Temporal integrity violation: {self.symbol} bar available at "
                f"{self.available_at.isoformat()} exceeds cutoff {cutoff.isoformat()}"
            )


@dataclass(frozen=True)
class MetricDefinition:
    name: str
    description: str
    formula: str
    required_inputs: tuple[str, ...]
    output_type: str
    version: str


@dataclass(frozen=True)
class MetricSnapshot:
    symbol: str
    observation_time: datetime
    prediction_cutoff: datetime
    max_source_available_at: datetime
    metric_version: str
    values: dict[str, float]

    def assert_temporal_integrity(self) -> None:
        if self.max_source_available_at > self.prediction_cutoff:
            raise ValueError(
                "Metric snapshot contains source data that was not available "
                "at prediction cutoff"
            )

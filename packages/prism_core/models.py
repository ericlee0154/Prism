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
    display_name: str
    display_name_zh: str
    description: str
    description_zh: str
    formula: str
    required_inputs: tuple[str, ...]
    output_type: str
    unit: str
    window_basis: str
    price_basis: str
    includes_current_session: bool
    minimum_observations: int
    ddof: int | None
    null_policy: str
    zero_denominator_policy: str
    calculation_cutoff: str
    version: str


@dataclass(frozen=True)
class MetricSnapshot:
    symbol: str
    observation_time: datetime
    prediction_cutoff: datetime
    max_source_available_at: datetime
    metric_version: str
    values: dict[str, float | None]

    def assert_temporal_integrity(self) -> None:
        if self.max_source_available_at > self.prediction_cutoff:
            raise ValueError(
                "Metric snapshot contains source data that was not available "
                "at prediction cutoff"
            )

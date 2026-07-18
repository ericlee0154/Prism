from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from ..models import Bar


class MarketDataProvider(ABC):
    name: str
    is_demo: bool

    @abstractmethod
    def bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
    ) -> list[Bar]:
        """Return bars whose availability timestamps can be independently audited."""

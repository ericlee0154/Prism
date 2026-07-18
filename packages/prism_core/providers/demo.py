from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ..models import Bar
from ..seed import DEMO_STOCKS
from .base import MarketDataProvider


class DemoMarketDataProvider(MarketDataProvider):
    name = "demo-seed"
    is_demo = True

    def bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
    ) -> list[Bar]:
        stock = DEMO_STOCKS.get(symbol.upper())
        if not stock:
            return []

        cutoff = datetime(2026, 7, 17, 20, 0, tzinfo=UTC)
        bars: list[Bar] = []
        base_price = stock["price"] * 0.72
        for index in range(130):
            timestamp = cutoff - timedelta(days=(129 - index))
            if timestamp.weekday() >= 5:
                continue
            normalized = stock["bars"][index % len(stock["bars"])] / 100
            drift = index * stock["price"] * 0.00155
            close = base_price + drift + normalized * stock["price"] * 0.035
            previous = bars[-1].close if bars else close * 0.995
            open_price = previous * (1 + ((index % 7) - 3) * 0.0007)
            high = max(open_price, close) * 1.008
            low = min(open_price, close) * 0.992
            available_at = timestamp.replace(hour=20, minute=0, second=0)
            if start <= timestamp <= end:
                bars.append(
                    Bar(
                        symbol=symbol.upper(),
                        timestamp=timestamp,
                        available_at=available_at,
                        open=round(open_price, 4),
                        high=round(high, 4),
                        low=round(low, 4),
                        close=round(close, 4),
                        volume=int(18_000_000 + index * 19_000 + normalized * 7_000_000),
                        source=self.name,
                    )
                )
        return bars

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

import httpx

from ..models import Bar
from .base import MarketDataProvider


class MassiveQuotaExceeded(RuntimeError):
    """Raised immediately when Massive refuses a request for quota reasons."""


class MassiveMarketDataProvider(MarketDataProvider):
    """Massive daily aggregate adapter with conservative availability times."""

    name = "massive"
    is_demo = False

    def __init__(
        self,
        api_key: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("MASSIVE_API_KEY")
        self.client = client

    def bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
    ) -> list[Bar]:
        if not self.api_key:
            raise RuntimeError(
                "MASSIVE_API_KEY is not configured. Use demo mode or add the key "
                "to the local environment."
            )

        ticker = symbol.strip().upper()
        if not ticker or len(ticker) > 12 or not ticker.replace(".", "").isalnum():
            raise ValueError("Invalid stock symbol")

        url = (
            f"https://api.massive.com/v2/aggs/ticker/{ticker}/range/1/day/"
            f"{start.date().isoformat()}/{end.date().isoformat()}"
        )
        parameters = {
            "adjusted": "true",
            "sort": "asc",
            "limit": "50000",
            "apiKey": self.api_key,
        }
        owns_client = self.client is None
        client = self.client or httpx.Client(timeout=15.0)
        try:
            response = client.get(url, params=parameters)
            if response.status_code == 429:
                raise MassiveQuotaExceeded(
                    f"Massive quota or rate limit reached for {ticker}; sync stopped"
                )
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
        except MassiveQuotaExceeded:
            raise
        except (httpx.HTTPError, ValueError) as error:
            raise RuntimeError(f"Massive request failed for {ticker}") from error
        finally:
            if owns_client:
                client.close()

        if payload.get("status") not in {"OK", "DELAYED"}:
            raise RuntimeError(f"Massive returned an unsuccessful status for {ticker}")

        bars: list[Bar] = []
        for item in payload.get("results", []):
            timestamp = datetime.fromtimestamp(float(item["t"]) / 1000, tz=UTC)
            # Daily stock aggregates are only eligible after the corresponding
            # regular session has closed. 21:05 UTC is conservative year-round.
            available_at = timestamp.replace(hour=21, minute=5, second=0, microsecond=0)
            if timestamp > end:
                continue
            bars.append(
                Bar(
                    symbol=ticker,
                    timestamp=timestamp,
                    available_at=available_at,
                    open=float(item["o"]),
                    high=float(item["h"]),
                    low=float(item["l"]),
                    close=float(item["c"]),
                    volume=int(item["v"]),
                    source=self.name,
                )
            )
        return bars

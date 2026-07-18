import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from packages.prism_core.ai_events import (
    AIResearchResult,
    CompanyEventFeed,
    CompanyEventItem,
    ConfidenceEvidenceItem,
    ConfidenceResearchFeed,
    EventOutcome,
    OpenAIEventResearchProvider,
    OpenAIQuotaExceeded,
    WorldEventFeed,
)
from packages.prism_core.codex_cli_events import (
    CodexCliEventResearchProvider,
    CodexCommandResult,
)
from packages.prism_core.models import Bar
from packages.prism_core.repository import PrismRepository
from packages.prism_core.service import PrismService


@pytest.fixture(autouse=True)
def disable_automatic_ai_provider(monkeypatch) -> None:
    monkeypatch.setenv("PRISM_AI_PROVIDER", "disabled")


def test_openai_event_provider_keeps_only_retrieved_sources() -> None:
    request_count = 0
    source_url = "https://example.com/central-bank"
    payload = {
        "as_of": "2026-07-18",
        "events": [
            {
                "title": "Central bank decision",
                "summary": "A scheduled policy decision.",
                "why_markets_care": "Rates can affect asset valuations.",
                "event_type": "central_bank",
                "status": "scheduled",
                "event_date_start": "2026-07-30",
                "event_date_end": "2026-07-30",
                "regions": ["US"],
                "affected_assets": ["equities", "bonds"],
                "watch_items": ["policy rate"],
                "importance": 5,
                "confidence": 0.9,
                "source_urls": [source_url, "https://invented.example/not-retrieved"],
            }
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        assert request.headers["Authorization"] == "Bearer test-secret"
        request_json = json.loads(request.content)
        assert request_json["store"] is False
        assert request_json["tools"][0]["type"] == "web_search"
        assert request_json["text"]["format"]["strict"] is True
        return httpx.Response(
            200,
            json={
                "id": "resp_test",
                "model": "gpt-5.6-sol",
                "usage": {"total_tokens": 100},
                "output": [
                    {
                        "type": "web_search_call",
                        "action": {
                            "type": "search",
                            "sources": [
                                {"url": source_url, "title": "Official source"}
                            ],
                        },
                    },
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(payload),
                                "annotations": [],
                            }
                        ],
                    },
                ],
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenAIEventResearchProvider(
        api_key="test-secret",
        model="gpt-5.6-sol",
        client=client,
    )
    result = provider.world_events(
        as_of=date(2026, 7, 18),
        lookback_days=7,
        lookahead_days=30,
    )
    client.close()

    assert request_count == 1
    assert result.response_id == "resp_test"
    assert len(result.payload.events) == 1
    assert result.payload.events[0].source_urls == [source_url]


def test_openai_event_provider_does_not_retry_quota() -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(429)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenAIEventResearchProvider(api_key="test-secret", client=client)
    with pytest.raises(OpenAIQuotaExceeded, match="refresh stopped"):
        provider.world_events(
            as_of=date(2026, 7, 18),
            lookback_days=7,
            lookahead_days=30,
        )
    client.close()
    assert request_count == 1


def test_codex_cli_provider_returns_schema_bound_grounded_output(
    monkeypatch,
) -> None:
    source_url = "https://example.com/official-event"
    captured: dict[str, object] = {}
    payload = {
        "as_of": "2026-07-18",
        "events": [
            {
                "title": "Policy decision",
                "summary": "A confirmed policy decision is scheduled.",
                "why_markets_care": "The decision can affect rates.",
                "event_type": "central_bank",
                "status": "scheduled",
                "event_date_start": "2026-07-30",
                "event_date_end": "2026-07-30",
                "regions": ["US"],
                "affected_assets": ["equities"],
                "watch_items": ["policy rate"],
                "importance": 5,
                "confidence": 0.9,
                "source_urls": [
                    source_url,
                    "https://invented.example/not-retrieved",
                ],
            }
        ],
    }

    def executor(command, prompt, timeout, environment):
        captured["command"] = command
        captured["prompt"] = prompt
        captured["timeout"] = timeout
        captured["environment"] = environment
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text(json.dumps(payload), encoding="utf-8")
        return CodexCommandResult(
            returncode=0,
            stdout="\n".join(
                [
                    json.dumps(
                        {
                            "type": "thread.started",
                            "thread_id": "thread_test",
                        }
                    ),
                    json.dumps(
                        {
                            "type": "item.completed",
                            "item": {
                                "type": "web_search",
                                "sources": [
                                    {
                                        "url": source_url,
                                        "title": "Official event",
                                    }
                                ],
                            },
                        }
                    ),
                    json.dumps(
                        {
                            "type": "turn.completed",
                            "usage": {"total_tokens": 123},
                        }
                    ),
                ]
            ),
            stderr="",
        )

    monkeypatch.setenv("MASSIVE_API_KEY", "must-not-reach-codex")
    provider = CodexCliEventResearchProvider(
        binary="/mock/codex",
        executor=executor,
        authenticated=True,
        timeout_seconds=60,
    )
    result = provider.world_events(
        as_of=date(2026, 7, 18),
        lookback_days=7,
        lookahead_days=30,
    )

    command = captured["command"]
    assert isinstance(command, list)
    assert "--search" in command
    assert "read-only" in command
    assert "--ephemeral" in command
    assert "--output-schema" in command
    model_index = command.index("--model")
    assert command[model_index + 1] == "gpt-5.6-sol"
    assert captured["environment"].get("MASSIVE_API_KEY") is None
    assert result.response_id == "thread_test"
    assert result.usage == {"total_tokens": 123}
    assert result.payload.events[0].source_urls == [source_url]


def test_codex_cli_provider_stops_on_chatgpt_usage_limit() -> None:
    calls = 0

    def executor(command, prompt, timeout, environment):
        nonlocal calls
        calls += 1
        return CodexCommandResult(
            returncode=1,
            stdout="",
            stderr="Usage limit reached",
        )

    provider = CodexCliEventResearchProvider(
        binary="/mock/codex",
        executor=executor,
        authenticated=True,
    )
    with pytest.raises(OpenAIQuotaExceeded, match="usage limit"):
        provider.world_events(
            as_of=date(2026, 7, 18),
            lookback_days=7,
            lookahead_days=30,
        )
    assert calls == 1


def test_codex_cli_provider_uses_safe_default_for_invalid_timeout(
    monkeypatch,
) -> None:
    monkeypatch.setenv("PRISM_CODEX_TIMEOUT_SECONDS", "not-a-number")
    provider = CodexCliEventResearchProvider(
        binary="/mock/codex",
        authenticated=True,
    )
    assert provider.timeout_seconds == 300
    assert provider.model == "gpt-5.6-sol"


def test_company_event_lifecycle_connects_forecast_and_market_reaction(
    tmp_path,
) -> None:
    repository = PrismRepository(tmp_path / "events.duckdb")
    repository.initialize()
    start = datetime(2025, 1, 1, 21, 0, tzinfo=UTC)
    symbol_bars = []
    benchmark_bars = []
    for index in range(150):
        timestamp = start + timedelta(days=index)
        symbol_bars.append(
            Bar(
                symbol="AAPL",
                timestamp=timestamp,
                available_at=timestamp,
                open=100 + index,
                high=102 + index,
                low=99 + index,
                close=101 + index,
                volume=1_000_000 + index * 10_000,
                source="massive",
            )
        )
        benchmark_bars.append(
            Bar(
                symbol="SPY",
                timestamp=timestamp,
                available_at=timestamp,
                open=500 + index / 2,
                high=502 + index / 2,
                low=499 + index / 2,
                close=501 + index / 2,
                volume=2_000_000,
                source="massive",
            )
        )
    repository.upsert_bars(symbol_bars + benchmark_bars)
    service = PrismService(repository)
    source_url = "https://investor.example.com/aapl-event"
    outcome_source_url = "https://investor.example.com/aapl-results"

    class FakeAIProvider:
        name = "openai"
        model = "test-model"
        configured = True

        def company_events(self, **kwargs):
            return AIResearchResult(
                payload=CompanyEventFeed(
                    as_of=date(2025, 3, 1),
                    symbol="AAPL",
                    events=[
                        CompanyEventItem(
                            symbol="AAPL",
                            title="Quarterly earnings",
                            summary="Scheduled quarterly results.",
                            event_type="earnings",
                            status="scheduled",
                            event_date_start=date(2025, 3, 20),
                            event_date_end=date(2025, 3, 20),
                            release_timing="after_market",
                            market_expectations=["Revenue growth"],
                            bullish_scenario="Results exceed stated expectations.",
                            bearish_scenario="Results miss stated expectations.",
                            watch_items=["guidance"],
                            importance=5,
                            confidence=0.95,
                            source_urls=[source_url],
                        )
                    ],
                ),
                response_id="resp_company",
                model=self.model,
                sources=[{"url": source_url, "title": "Investor relations"}],
                usage={"total_tokens": 10},
            )

        def event_outcome(self, **kwargs):
            return AIResearchResult(
                payload=EventOutcome(
                    event_status="occurred",
                    actual_event_date=date(2025, 3, 20),
                    actual_results=["Results were published."],
                    surprise_summary="Outcome recorded from the official release.",
                    interpretation="Research note only.",
                    follow_up_items=["Next guidance update"],
                    confidence=0.95,
                    source_urls=[outcome_source_url],
                ),
                response_id="resp_outcome",
                model=self.model,
                sources=[
                    {
                        "url": outcome_source_url,
                        "title": "Official results",
                    }
                ],
                usage={"total_tokens": 10},
            )

    service.ai_provider = FakeAIProvider()
    refreshed = service.refresh_company_events(
        symbol="AAPL",
        start_date=date(2025, 3, 15),
        end_date=date(2025, 6, 1),
    )
    event_id = refreshed["events"][0]["event_id"]

    analysis = service.analyze_range(
        "AAPL",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 3, 10),
    )
    assert analysis["scheduled_events"][0]["event_id"] == event_id
    assert 30 in analysis["scheduled_events"][0]["forecast_horizons"]

    resolved = service.resolve_event(event_id)
    event = resolved["event"]
    assert event["status"] == "occurred"
    assert event["actual"]["actual_results"] == ["Results were published."]
    assert {source["url"] for source in event["sources"]} == {
        source_url,
        outcome_source_url,
    }
    assert event["reaction"]["status"] == "complete"
    assert event["reaction"]["returns"]["1_session"]["symbol_return"] is not None
    repository.close()


def test_weekly_institution_and_monthly_long_term_confidence_are_versioned(
    tmp_path,
) -> None:
    repository = PrismRepository(tmp_path / "confidence.duckdb")
    repository.initialize()
    start = datetime(2025, 1, 1, 21, 0, tzinfo=UTC)
    repository.upsert_bars(
        [
            Bar(
                symbol="AAPL",
                timestamp=start + timedelta(days=index),
                available_at=start + timedelta(days=index),
                open=100 + index / 2,
                high=102 + index / 2,
                low=99 + index / 2,
                close=101 + index / 2,
                volume=1_000_000,
                source="massive",
            )
            for index in range(300)
        ]
    )
    service = PrismService(repository)
    source_url = "https://example.com/institution-view"

    class FakeConfidenceProvider:
        name = "openai"
        model = "test-model"
        configured = True

        def confidence_evidence(self, **kwargs):
            return AIResearchResult(
                payload=ConfidenceResearchFeed(
                    as_of=date.today(),
                    symbol="AAPL",
                    evidence=[
                        ConfidenceEvidenceItem(
                            institution="Example Bank",
                            category="institutional_outlook",
                            stance=1,
                            statement="The institution published a positive outlook.",
                            rationale="Product execution was cited.",
                            published_date=date.today(),
                            confidence=0.8,
                            source_urls=[source_url],
                        ),
                        ConfidenceEvidenceItem(
                            institution=None,
                            category="product",
                            stance=2,
                            statement="A product milestone was announced.",
                            rationale="The milestone supports the brand evidence component.",
                            published_date=date.today(),
                            confidence=0.9,
                            source_urls=[source_url],
                        ),
                    ],
                ),
                response_id="resp_confidence",
                model=self.model,
                sources=[{"url": source_url, "title": "Retrieved source"}],
                usage={"total_tokens": 10},
            )

    service.ai_provider = FakeConfidenceProvider()
    result = service.refresh_confidence(symbol="AAPL")
    institution = next(
        item for item in result["snapshots"] if item["dimension"] == "institution"
    )
    long_term = next(
        item
        for item in result["snapshots"]
        if item["dimension"] == "company_long_term"
    )
    assert institution["frequency"] == "weekly"
    assert institution["entity"] == "Example Bank"
    assert institution["score"] == 75.0
    assert long_term["frequency"] == "monthly"
    assert long_term["coverage_status"] == "complete"
    assert long_term["components"]["scores"]["market_price"] is not None
    assert repository.list_confidence_snapshots(symbol="AAPL") != []
    repository.close()

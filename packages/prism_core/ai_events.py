from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal, TypeVar
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field


PROMPT_VERSION = "event-research-v0.3"
DEFAULT_EVENT_MODEL = "gpt-5.6-sol"


class OpenAIQuotaExceeded(RuntimeError):
    """Raised immediately when the AI provider returns a quota/rate limit."""


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResearchSourceReference(StrictModel):
    url: str
    language: Literal["EN", "ZH", "JA", "KO", "OTHER", "UNKNOWN"]


class WorldEventTranslationZh(StrictModel):
    title: str
    summary: str
    why_markets_care: str
    watch_items: list[str]


class WorldEventItem(StrictModel):
    title: str
    summary: str
    why_markets_care: str
    event_type: Literal[
        "geopolitical",
        "central_bank",
        "regulation",
        "commodity",
        "technology",
        "health",
        "climate",
        "conflict",
        "election",
        "macro",
        "other",
    ]
    status: Literal["scheduled", "ongoing", "occurred", "date_uncertain"]
    event_date_start: date | None = Field(...)
    event_date_end: date | None = Field(...)
    regions: list[str]
    affected_assets: list[str]
    watch_items: list[str]
    importance: int = Field(ge=1, le=5)
    confidence: float = Field(ge=0, le=1)
    translation_zh: WorldEventTranslationZh
    source_references: list[ResearchSourceReference]


class WorldEventFeed(StrictModel):
    as_of: date
    events: list[WorldEventItem]


class CompanyEventTranslationZh(StrictModel):
    title: str
    summary: str
    market_expectations: list[str]
    bullish_scenario: str
    bearish_scenario: str
    watch_items: list[str]


class CompanyEventItem(StrictModel):
    symbol: str
    title: str
    summary: str
    event_type: Literal[
        "earnings",
        "product_launch",
        "investor_day",
        "conference",
        "regulatory_decision",
        "capital_action",
        "legal",
        "macro_exposure",
        "other",
    ]
    status: Literal["scheduled", "occurred", "cancelled", "date_uncertain"]
    event_date_start: date | None = Field(...)
    event_date_end: date | None = Field(...)
    release_timing: Literal[
        "before_market",
        "during_market",
        "after_market",
        "unknown",
    ]
    market_expectations: list[str]
    bullish_scenario: str
    bearish_scenario: str
    watch_items: list[str]
    importance: int = Field(ge=1, le=5)
    confidence: float = Field(ge=0, le=1)
    translation_zh: CompanyEventTranslationZh
    source_references: list[ResearchSourceReference]


class CompanyEventFeed(StrictModel):
    as_of: date
    symbol: str
    events: list[CompanyEventItem]


class EventOutcome(StrictModel):
    event_status: Literal["occurred", "cancelled", "not_yet_available"]
    actual_event_date: date | None = Field(...)
    actual_results: list[str]
    surprise_summary: str
    interpretation: str
    follow_up_items: list[str]
    confidence: float = Field(ge=0, le=1)
    source_urls: list[str]


class ConfidenceEvidenceItem(StrictModel):
    institution: str | None = Field(...)
    category: Literal[
        "institutional_rating",
        "institutional_outlook",
        "capital_allocation",
        "product",
        "customer",
        "competitive",
        "reputation",
        "regulatory",
    ]
    stance: Literal[-2, -1, 0, 1, 2]
    statement: str
    rationale: str
    published_date: date
    confidence: float = Field(ge=0, le=1)
    source_urls: list[str]


class ConfidenceResearchFeed(StrictModel):
    as_of: date
    symbol: str
    evidence: list[ConfidenceEvidenceItem]


@dataclass(frozen=True)
class AIResearchResult:
    payload: BaseModel
    response_id: str
    model: str
    sources: list[dict[str, str]]
    usage: dict[str, Any]


SchemaT = TypeVar("SchemaT", bound=BaseModel)


class OpenAIEventResearchProvider:
    """Grounded event research via Responses API web search."""

    name = "openai"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "").strip()
        self.model = (
            model or os.getenv("OPENAI_EVENT_MODEL", "").strip() or DEFAULT_EVENT_MODEL
        )
        self.client = client

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def world_events(
        self,
        *,
        as_of: date,
        lookback_days: int,
        lookahead_days: int,
    ) -> AIResearchResult:
        return self._request(
            schema_model=WorldEventFeed,
            schema_name="world_event_feed",
            instructions=(
                "Role: grounded global market event researcher. "
                "Find only material world events with plausible effects on liquid markets. "
                "Use live web search. Prefer central banks, governments, regulators, "
                "international organizations, and established reporting. "
                "Write the primary title, summary, analysis, and watch items in English. "
                "Also provide a faithful Traditional Chinese translation in translation_zh; "
                "the translation must add no facts or interpretation. "
                "Every event must include at least one source_references entry whose exact URL "
                "was retrieved in this run. Label each page's actual source language as EN, ZH, "
                "JA, KO, OTHER, or UNKNOWN. "
                "Return no event when evidence or dates are too weak. "
                "Separate confirmed facts from market interpretation. "
                "Do not invent prices, forecasts, consensus estimates, or dates."
            ),
            input_text=(
                f"As of {as_of.isoformat()}, identify up to 12 market-relevant world "
                f"events from the prior {lookback_days} days and scheduled within the "
                f"next {lookahead_days} days. Include ongoing geopolitical, macro, "
                "central-bank, regulatory, commodity, technology, health, climate, "
                "conflict, and election developments only when materially relevant."
            ),
            max_tool_calls=5,
        )

    def company_events(
        self,
        *,
        symbol: str,
        start_date: date,
        end_date: date,
        as_of: date,
    ) -> AIResearchResult:
        ticker = symbol.strip().upper()
        return self._request(
            schema_model=CompanyEventFeed,
            schema_name="company_event_feed",
            instructions=(
                "Role: grounded public-company event researcher. "
                "Use live web search and prioritize the company's investor-relations site, "
                "SEC filings, exchanges, and regulators; use established reporting second. "
                "Track earnings, product launches, investor days, conferences, regulatory "
                "decisions, capital actions, and material legal events. "
                "Write the primary title, summary, expectations, scenarios, and watch items "
                "in English. Also provide a faithful Traditional Chinese translation in "
                "translation_zh; the translation must add no facts or interpretation. "
                "Every event must include at least one source_references entry whose exact URL "
                "was retrieved in this run. Label each page's actual source language as EN, ZH, "
                "JA, KO, OTHER, or UNKNOWN. "
                "Return no event when evidence is insufficient. "
                "Market expectations and scenarios must be clearly labeled analysis, not fact. "
                "Do not invent prices, dates, consensus estimates, or results."
            ),
            input_text=(
                f"As of {as_of.isoformat()}, research {ticker} events between "
                f"{start_date.isoformat()} and {end_date.isoformat()}. "
                f"The symbol field must be exactly {ticker}. Include up to 12 events."
            ),
            max_tool_calls=4,
        )

    def event_outcome(
        self,
        *,
        event: dict[str, Any],
        as_of: date,
    ) -> AIResearchResult:
        return self._request(
            schema_model=EventOutcome,
            schema_name="event_outcome",
            instructions=(
                "Role: grounded post-event research recorder. "
                "Use live web search. Prefer official company releases, filings, regulators, "
                "and exchanges. Record only results that are now public. "
                "Every result must include exact source URLs retrieved in this run. "
                "If the event has not happened or results are unavailable, return "
                "not_yet_available with empty actual_results. "
                "Do not invent prices or market reactions; the application calculates those."
            ),
            input_text=(
                f"As of {as_of.isoformat()}, resolve this recorded event:\n"
                f"{json.dumps(event, sort_keys=True, default=str)}"
            ),
            max_tool_calls=4,
        )

    def confidence_evidence(
        self,
        *,
        symbol: str,
        as_of: date,
        lookback_days: int = 45,
    ) -> AIResearchResult:
        ticker = symbol.strip().upper()
        return self._request(
            schema_model=ConfidenceResearchFeed,
            schema_name="confidence_research_feed",
            instructions=(
                "Role: grounded company confidence evidence researcher. "
                "Use live web search. Collect recent, attributable evidence from named "
                "banks, asset managers, research firms, the company, regulators, and "
                "credible reporting. Institutional evidence must name the institution. "
                "Brand evidence may cover products, customers, competition, reputation, "
                "or regulation and uses a null institution. "
                "Stance is an ordinal evidence label: -2 strongly negative, -1 negative, "
                "0 mixed/neutral, 1 positive, 2 strongly positive. It is not a price target. "
                "Every item must include an exact source URL retrieved in this run. "
                "Return an empty evidence list when public evidence is insufficient. "
                "Do not invent ratings, surveys, market shares, dates, or quotations."
            ),
            input_text=(
                f"As of {as_of.isoformat()}, research public confidence evidence for "
                f"{ticker} published within the prior {lookback_days} days. Include up "
                "to 20 distinct evidence items. The symbol field must be exactly "
                f"{ticker}. Prefer primary sources and preserve distinct institutions."
            ),
            max_tool_calls=5,
        )

    def _request(
        self,
        *,
        schema_model: type[SchemaT],
        schema_name: str,
        instructions: str,
        input_text: str,
        max_tool_calls: int,
    ) -> AIResearchResult:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")

        body = {
            "model": self.model,
            "store": False,
            "reasoning": {"effort": "low"},
            "tools": [
                {
                    "type": "web_search",
                    "search_context_size": "medium",
                    "external_web_access": True,
                }
            ],
            "tool_choice": "required",
            "include": ["web_search_call.action.sources"],
            "max_tool_calls": max_tool_calls,
            "max_output_tokens": 6000,
            "instructions": instructions,
            "input": input_text,
            "text": {
                "verbosity": "medium",
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "strict": True,
                    "schema": schema_model.model_json_schema(),
                },
            },
            "metadata": {
                "application": "prism",
                "prompt_version": PROMPT_VERSION,
                "task": schema_name,
            },
        }
        owns_client = self.client is None
        client = self.client or httpx.Client(timeout=120.0)
        try:
            response = client.post(
                "https://api.openai.com/v1/responses",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            if response.status_code == 429:
                raise OpenAIQuotaExceeded(
                    "OpenAI quota or rate limit reached; AI event refresh stopped"
                )
            response.raise_for_status()
            raw: dict[str, Any] = response.json()
        except OpenAIQuotaExceeded:
            raise
        except (httpx.HTTPError, ValueError) as error:
            raise RuntimeError("OpenAI event research request failed") from error
        finally:
            if owns_client:
                client.close()

        output_text, annotation_sources, refusal = _extract_message(raw)
        if refusal:
            raise RuntimeError(f"OpenAI event research refused: {refusal}")
        if not output_text:
            raise RuntimeError("OpenAI event research returned no structured output")
        try:
            payload = schema_model.model_validate_json(output_text)
        except (ValueError, TypeError) as error:
            raise RuntimeError("OpenAI event research returned invalid structured output") from error

        sources = _extract_sources(raw, annotation_sources)
        payload = _retain_grounded_items(payload, sources)
        return AIResearchResult(
            payload=payload,
            response_id=str(raw.get("id", "")),
            model=str(raw.get("model", self.model)),
            sources=sources,
            usage=dict(raw.get("usage") or {}),
        )


def _extract_message(
    raw: dict[str, Any],
) -> tuple[str, list[dict[str, str]], str | None]:
    texts: list[str] = []
    sources: list[dict[str, str]] = []
    refusal: str | None = None
    for output in raw.get("output", []):
        if output.get("type") != "message":
            continue
        for item in output.get("content", []):
            if item.get("type") == "refusal":
                refusal = str(item.get("refusal", "Request refused"))
            if item.get("type") != "output_text":
                continue
            texts.append(str(item.get("text", "")))
            for annotation in item.get("annotations", []):
                if annotation.get("type") != "url_citation":
                    continue
                sources.append(
                    {
                        "url": str(annotation.get("url", "")),
                        "title": str(annotation.get("title", "")),
                    }
                )
    return "".join(texts), sources, refusal


def _extract_sources(
    raw: dict[str, Any],
    annotation_sources: list[dict[str, str]],
) -> list[dict[str, str]]:
    candidates = list(annotation_sources)
    for output in raw.get("output", []):
        if output.get("type") != "web_search_call":
            continue
        action = output.get("action") or {}
        for source in action.get("sources") or []:
            candidates.append(
                {
                    "url": str(source.get("url", "")),
                    "title": str(source.get("title", "")),
                }
            )
    unique: dict[str, dict[str, str]] = {}
    for source in candidates:
        canonical = _canonical_url(source.get("url", ""))
        if canonical:
            unique[canonical] = {
                "url": source["url"],
                "title": source.get("title", ""),
            }
    return list(unique.values())


def _retain_grounded_items(
    payload: SchemaT,
    sources: list[dict[str, str]],
) -> SchemaT:
    if hasattr(payload, "evidence"):
        grounded_evidence = []
        for item in getattr(payload, "evidence"):
            matched = _matched_urls(item.source_urls, sources)
            if matched:
                grounded_evidence.append(item.model_copy(update={"source_urls": matched}))
        return payload.model_copy(update={"evidence": grounded_evidence})

    if not hasattr(payload, "events"):
        if hasattr(payload, "source_urls"):
            matched = _matched_urls(getattr(payload, "source_urls"), sources)
            if getattr(payload, "event_status", None) == "not_yet_available":
                return payload.model_copy(update={"source_urls": matched})
            if not matched:
                raise RuntimeError("AI event outcome contained no retrieved source URL")
            return payload.model_copy(update={"source_urls": matched})
        return payload

    grounded = []
    for event in getattr(payload, "events"):
        if hasattr(event, "source_references"):
            matched_references = _matched_source_references(
                event.source_references,
                sources,
            )
            if matched_references:
                grounded.append(
                    event.model_copy(
                        update={"source_references": matched_references}
                    )
                )
            continue
        matched = _matched_urls(event.source_urls, sources)
        if matched:
            grounded.append(event.model_copy(update={"source_urls": matched}))
    return payload.model_copy(update={"events": grounded})


def _matched_source_references(
    references: list[ResearchSourceReference],
    sources: list[dict[str, str]],
) -> list[ResearchSourceReference]:
    source_map = {
        _canonical_url(source.get("url", "")): source.get("url", "")
        for source in sources
    }
    matched: list[ResearchSourceReference] = []
    for reference in references:
        canonical = _canonical_url(reference.url)
        if canonical in source_map:
            matched.append(
                reference.model_copy(update={"url": source_map[canonical]})
            )
    return matched


def _matched_urls(
    urls: list[str],
    sources: list[dict[str, str]],
) -> list[str]:
    source_map = {
        _canonical_url(source.get("url", "")): source.get("url", "")
        for source in sources
    }
    matched: list[str] = []
    for url in urls:
        canonical = _canonical_url(url)
        if canonical and canonical in source_map:
            matched.append(source_map[canonical])
    return list(dict.fromkeys(matched))


def _canonical_url(value: str) -> str:
    try:
        parts = urlsplit(value)
    except ValueError:
        return ""
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return ""
    query = [
        (key, item)
        for key, item in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_")
    ]
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path.rstrip("/"),
            urlencode(query),
            "",
        )
    )

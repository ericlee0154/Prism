from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from packages.prism_core.ai_events import OpenAIQuotaExceeded
from packages.prism_core.repository import PrismRepository
from packages.prism_core.service import PrismService


ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
DATABASE_PATH = Path(
    os.getenv("PRISM_DATABASE_PATH", ROOT / "data" / "prism.duckdb")
)


def create_repository() -> PrismRepository:
    return PrismRepository(DATABASE_PATH)


def get_service() -> PrismService:
    return app.state.service


@asynccontextmanager
async def lifespan(application: FastAPI):
    repository = create_repository()
    repository.initialize()
    service = PrismService(repository)
    application.state.repository = repository
    application.state.service = service
    yield
    repository.close()


app = FastAPI(
    title="Prism Research API",
    description=(
        "Local-first endpoints for point-in-time market metrics, formula research, "
        "and immutable forward predictions."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1):\d+$",
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

Service = Annotated[PrismService, Depends(get_service)]
Horizon = Literal["10D", "30D", "90D"]


class SealPredictionRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=12)
    horizon: Horizon = "30D"
    formula_version: str = Field(default="core-v0.1", min_length=1, max_length=80)


class SyncRequest(BaseModel):
    symbols: list[str] = Field(min_length=1, max_length=100)
    years: int = Field(default=2, ge=1, le=20)
    start_date: date | None = None
    end_date: date | None = None


class BacktestRequest(BaseModel):
    horizon_sessions: Literal[10, 30, 90] = 30


class AnalysisRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=12)
    start_date: date
    end_date: date


class WorldEventRefreshRequest(BaseModel):
    lookback_days: int = Field(default=7, ge=1, le=90)
    lookahead_days: int = Field(default=30, ge=1, le=180)


class CompanyEventRefreshRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=12)
    start_date: date
    end_date: date


class DueEventResolveRequest(BaseModel):
    limit: int = Field(default=5, ge=1, le=20)


class ConfidenceRefreshRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=12)


@app.get("/api/v1/health")
def health(service: Service) -> dict:
    summary = service.repository.market_summary()
    return {
        "status": "ok",
        "service": "prism-api",
        "version": app.version,
        "provider": service.provider_name,
        "provider_configured": service.provider_configured,
        "ai_provider": service.ai_provider_name,
        "ai_provider_configured": service.ai_configured,
        "ai_configuration_error": service.ai_configuration_error,
        "ai_model": service.ai_model,
        "mode": "live" if summary["bar_count"] else "empty",
        "data_cutoff": summary["data_cutoff"],
        "database": str(DATABASE_PATH),
        "server_time": datetime.now(UTC).isoformat(),
    }


@app.get("/api/v1/overview")
def overview(service: Service) -> dict:
    return service.overview()


@app.get("/api/v1/scanner")
def scanner(
    service: Service,
    horizon: Horizon = Query(default="30D"),
    search: str = Query(default="", max_length=80),
) -> dict:
    summary = service.repository.market_summary()
    return {
        "horizon": horizon,
        "data_cutoff": summary["data_cutoff"],
        "provider": service.provider_name,
        "items": service.scan(horizon=horizon, search=search),
    }


@app.get("/api/v1/stocks/{symbol}")
def stock_detail(symbol: str, service: Service) -> dict:
    result = service.stock_detail(symbol.upper())
    if result is None:
        raise HTTPException(status_code=404, detail=f"Unknown symbol: {symbol}")
    return result


@app.get("/api/v1/metrics/catalog")
def metric_catalog(service: Service) -> dict:
    return service.metric_methodology()


@app.get("/api/v1/predictions")
def predictions(
    service: Service,
    horizon: Horizon | None = Query(default=None),
    outcome: Literal["Pending", "Correct", "Incorrect"] | None = Query(default=None),
) -> dict:
    return {"items": service.predictions(horizon=horizon, outcome=outcome)}


@app.post("/api/v1/predictions/seal", status_code=201)
def seal_prediction(request: SealPredictionRequest, service: Service) -> dict:
    symbol = request.symbol.upper()
    try:
        return service.seal_prediction(
            symbol=symbol,
            horizon=request.horizon,
            formula_version=request.formula_version,
        )
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/v1/pipeline")
def pipeline(service: Service) -> dict:
    return service.pipeline_status()


@app.post("/api/v1/sync")
def sync_market_data(request: SyncRequest, service: Service) -> dict:
    try:
        return service.sync_market_data(
            request.symbols,
            request.years,
            start_date=request.start_date,
            end_date=request.end_date,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/api/v1/backtests", status_code=201)
def create_backtest(request: BacktestRequest, service: Service) -> dict:
    return service.run_backtest(request.horizon_sessions)


@app.get("/api/v1/backtests")
def list_backtests(service: Service) -> dict:
    return {"items": service.repository.list_backtests()}


@app.post("/api/v1/analyses", status_code=201)
def create_analysis(request: AnalysisRequest, service: Service) -> dict:
    try:
        return service.analyze_range(
            request.symbol,
            start_date=request.start_date,
            end_date=request.end_date,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/api/v1/analyses")
def list_analyses(service: Service) -> dict:
    return {"items": service.repository.list_range_analyses()}


@app.get("/api/v1/events")
def list_events(
    service: Service,
    scope: Literal["world", "company"] | None = Query(default=None),
    symbol: str | None = Query(default=None, max_length=12),
    limit: int = Query(default=200, ge=1, le=500),
) -> dict:
    return service.event_center(scope=scope, symbol=symbol, limit=limit)


@app.get("/api/v1/instruments/classifications")
def instrument_classifications(service: Service) -> dict:
    return service.instrument_classification_center()


@app.post("/api/v1/instruments/classifications/refresh", status_code=201)
def refresh_instrument_classifications(service: Service) -> dict:
    try:
        return service.refresh_instrument_classifications()
    except OpenAIQuotaExceeded as error:
        raise HTTPException(status_code=429, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/api/v1/events/world/refresh", status_code=201)
def refresh_world_events(
    request: WorldEventRefreshRequest,
    service: Service,
) -> dict:
    try:
        return service.refresh_world_events(
            lookback_days=request.lookback_days,
            lookahead_days=request.lookahead_days,
        )
    except OpenAIQuotaExceeded as error:
        raise HTTPException(status_code=429, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/api/v1/events/company/refresh", status_code=201)
def refresh_company_events(
    request: CompanyEventRefreshRequest,
    service: Service,
) -> dict:
    try:
        return service.refresh_company_events(
            symbol=request.symbol,
            start_date=request.start_date,
            end_date=request.end_date,
        )
    except OpenAIQuotaExceeded as error:
        raise HTTPException(status_code=429, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/api/v1/events/due/resolve")
def resolve_due_events(
    request: DueEventResolveRequest,
    service: Service,
) -> dict:
    try:
        return service.resolve_due_events(limit=request.limit)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.post("/api/v1/events/reactions/refresh")
def refresh_event_reactions(service: Service) -> dict:
    return service.recompute_event_reactions()


@app.post("/api/v1/events/{event_id}/resolve")
def resolve_event(event_id: str, service: Service) -> dict:
    try:
        return service.resolve_event(event_id)
    except OpenAIQuotaExceeded as error:
        raise HTTPException(status_code=429, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.get("/api/v1/confidence")
def confidence_snapshots(
    service: Service,
    symbol: str | None = Query(default=None, max_length=12),
    limit: int = Query(default=500, ge=1, le=1000),
) -> dict:
    return service.confidence_center(symbol=symbol, limit=limit)


@app.post("/api/v1/confidence/refresh", status_code=201)
def refresh_confidence(
    request: ConfidenceRefreshRequest,
    service: Service,
) -> dict:
    try:
        return service.refresh_confidence(symbol=request.symbol)
    except OpenAIQuotaExceeded as error:
        raise HTTPException(status_code=429, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.get("/")
def root() -> dict:
    return {
        "name": "Prism Research API",
        "docs": "/docs",
        "health": "/api/v1/health",
    }

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


@app.get("/api/v1/health")
def health(service: Service) -> dict:
    summary = service.repository.market_summary()
    return {
        "status": "ok",
        "service": "prism-api",
        "version": app.version,
        "provider": service.provider_name,
        "provider_configured": service.provider_configured,
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
    return {"items": service.metric_catalog()}


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


@app.get("/")
def root() -> dict:
    return {
        "name": "Prism Research API",
        "docs": "/docs",
        "health": "/api/v1/health",
    }

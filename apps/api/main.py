from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from packages.prism_core.repository import PrismRepository
from packages.prism_core.seed import DEMO_STOCKS
from packages.prism_core.service import FormulaWeights, PrismService


ROOT = Path(__file__).resolve().parents[2]
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
    service.ensure_demo_data()
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
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

Service = Annotated[PrismService, Depends(get_service)]
Horizon = Literal["10D", "30D", "90D"]


class FormulaRequest(BaseModel):
    horizon: Horizon = "30D"
    weights: FormulaWeights
    formula_version: str = Field(default="candidate-v0.1", min_length=1, max_length=80)


class SealPredictionRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=12)
    horizon: Horizon = "30D"
    formula_version: str = Field(default="core-v0.1", min_length=1, max_length=80)


@app.get("/api/v1/health")
def health(service: Service) -> dict:
    return {
        "status": "ok",
        "service": "prism-api",
        "version": app.version,
        "provider": service.provider_name,
        "mode": "demo" if service.is_demo else "live",
        "data_cutoff": service.data_cutoff.isoformat(),
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
    return {
        "horizon": horizon,
        "data_cutoff": service.data_cutoff.isoformat(),
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


@app.post("/api/v1/formulas/evaluate")
def evaluate_formula(request: FormulaRequest, service: Service) -> dict:
    return service.evaluate_formula(
        horizon=request.horizon,
        weights=request.weights,
        formula_version=request.formula_version,
    )


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
    if symbol not in DEMO_STOCKS:
        raise HTTPException(status_code=404, detail=f"Unknown symbol: {symbol}")
    return service.seal_prediction(
        symbol=symbol,
        horizon=request.horizon,
        formula_version=request.formula_version,
    )


@app.get("/api/v1/pipeline")
def pipeline(service: Service) -> dict:
    return service.pipeline_status()


@app.post("/api/v1/sync")
def sync_demo(service: Service) -> dict:
    service.ensure_demo_data(force=True)
    return {
        "status": "complete",
        "provider": service.provider_name,
        "mode": "demo",
        "symbols": len(DEMO_STOCKS),
        "data_cutoff": service.data_cutoff.isoformat(),
    }


@app.get("/")
def root() -> dict:
    return {
        "name": "Prism Research API",
        "docs": "/docs",
        "health": "/api/v1/health",
    }

from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime
from typing import Callable, Sequence
from uuid import uuid4

from .forecast import historical_analog_forecast
from .models import Bar


MAX_SURFACE_POINTS = 80
MIN_ANALOG_SAMPLES = 30
MIN_SURFACE_POINTS = 5
SUPPORTED_HORIZONS = {10, 30, 90}


def required_surface_sessions(horizon_sessions: int) -> int:
    if horizon_sessions not in SUPPORTED_HORIZONS:
        raise ValueError("Horizon must be 10, 30, or 90 sessions")
    # 60 sessions for the feature vector, 30 completed historical analogs,
    # two horizon spans (analog outcome + forecast target), and five target
    # points for a minimally useful surface.
    return (
        60
        + MIN_ANALOG_SAMPLES
        + 2 * horizon_sessions
        + MIN_SURFACE_POINTS
        - 1
    )


def _sample_indices(indices: list[int], maximum: int) -> list[int]:
    if len(indices) <= maximum:
        return indices
    last = len(indices) - 1
    sampled = {
        indices[round(position * last / (maximum - 1))]
        for position in range(maximum)
    }
    return sorted(sampled)


async def compute_forecast_surface(
    bars: Sequence[Bar],
    *,
    horizon_sessions: int,
    progress: Callable[[int], None],
) -> dict:
    if horizon_sessions not in SUPPORTED_HORIZONS:
        raise ValueError("Horizon must be 10, 30, or 90 sessions")
    ordered = sorted(bars, key=lambda bar: bar.timestamp)
    required = required_surface_sessions(horizon_sessions)
    if len(ordered) < required:
        return {
            "status": "insufficient_data",
            "horizon_sessions": horizon_sessions,
            "bar_count": len(ordered),
            "required_sessions": required,
            "minimum_surface_points": MIN_SURFACE_POINTS,
            "minimum_analog_samples": MIN_ANALOG_SAMPLES,
            "points": [],
        }

    first_target_index = (
        60 + MIN_ANALOG_SAMPLES + 2 * horizon_sessions - 1
    )
    target_indices = _sample_indices(
        list(range(first_target_index, len(ordered))),
        MAX_SURFACE_POINTS,
    )
    points: list[dict] = []
    for position, target_index in enumerate(target_indices):
        await asyncio.sleep(0)
        origin_index = target_index - horizon_sessions
        training_bars = ordered[: origin_index + 1]
        forecast = historical_analog_forecast(
            training_bars,
            horizon_sessions=horizon_sessions,
            analog_count=MIN_ANALOG_SAMPLES,
        )
        if forecast["status"] == "complete":
            target = ordered[target_index]
            points.append(
                {
                    "origin_date": ordered[origin_index]
                    .timestamp.astimezone(UTC)
                    .date().isoformat(),
                    "target_date": target.timestamp.astimezone(UTC)
                    .date().isoformat(),
                    "actual_price": target.close,
                    "p10_price": forecast["p10_price"],
                    "p50_price": forecast["p50_price"],
                    "p90_price": forecast["p90_price"],
                    "sample_count": forecast["sample_count"],
                }
            )
        progress(round(100 * (position + 1) / len(target_indices)))

    return {
        "status": "complete",
        "horizon_sessions": horizon_sessions,
        "bar_count": len(ordered),
        "required_sessions": required,
        "minimum_surface_points": MIN_SURFACE_POINTS,
        "minimum_analog_samples": MIN_ANALOG_SAMPLES,
        "point_count": len(points),
        "candidate_point_count": (
            len(ordered) - first_target_index
        ),
        "sampling_interval_sessions": (
            max(
                1,
                round(
                    (len(ordered) - first_target_index - 1)
                    / max(len(target_indices) - 1, 1)
                ),
            )
        ),
        "data_cutoff": max(bar.available_at for bar in ordered).isoformat(),
        "selected_start": ordered[0]
        .timestamp.astimezone(UTC)
        .date().isoformat(),
        "selected_end": ordered[-1]
        .timestamp.astimezone(UTC)
        .date().isoformat(),
        "sources": [
            "actual_price",
            "p10_price",
            "p50_price",
            "p90_price",
        ],
        "points": points,
    }


class ForecastSurfaceJobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, dict] = {}
        self._key_to_job: dict[str, str] = {}

    def submit(
        self,
        *,
        symbol: str,
        start_date: str,
        end_date: str,
        horizon_sessions: int,
        bars: Sequence[Bar],
    ) -> dict:
        data_signature = hashlib.sha256(
            "\n".join(
                (
                    f"{bar.timestamp.isoformat()}|{bar.available_at.isoformat()}|"
                    f"{bar.close:.12g}|{bar.volume}"
                )
                for bar in sorted(bars, key=lambda item: item.timestamp)
            ).encode("utf-8")
        ).hexdigest()
        request_key = hashlib.sha256(
            "|".join(
                [
                    symbol.upper(),
                    start_date,
                    end_date,
                    str(horizon_sessions),
                    str(len(bars)),
                    data_signature,
                ]
            ).encode("utf-8")
        ).hexdigest()
        existing_id = self._key_to_job.get(request_key)
        if existing_id and existing_id in self._jobs:
            existing = self._jobs[existing_id]
            if existing["status"] not in {"cancelled", "failed"}:
                return self._snapshot(existing)

        job_id = str(uuid4())
        job = {
            "job_id": job_id,
            "request_key": request_key,
            "status": "queued",
            "progress": 0,
            "created_at": datetime.now(UTC).isoformat(),
            "symbol": symbol.upper(),
            "start_date": start_date,
            "end_date": end_date,
            "horizon_sessions": horizon_sessions,
            "result": None,
            "error": None,
            "task": None,
        }
        self._jobs[job_id] = job
        self._key_to_job[request_key] = job_id
        job["task"] = asyncio.create_task(
            self._run(job, list(bars)),
            name=f"forecast-surface-{job_id}",
        )
        self._prune()
        return self._snapshot(job)

    async def _run(self, job: dict, bars: list[Bar]) -> None:
        job["status"] = "running"
        try:
            result = await compute_forecast_surface(
                bars,
                horizon_sessions=job["horizon_sessions"],
                progress=lambda value: job.update(progress=value),
            )
            job["result"] = result
            job["progress"] = 100
            job["status"] = result["status"]
        except asyncio.CancelledError:
            job["status"] = "cancelled"
            job["error"] = None
        except Exception as error:
            job["status"] = "failed"
            job["error"] = str(error)

    def get(self, job_id: str) -> dict:
        job = self._jobs.get(job_id)
        if not job:
            raise ValueError("Forecast surface job not found")
        return self._snapshot(job)

    def cancel(self, job_id: str) -> dict:
        job = self._jobs.get(job_id)
        if not job:
            raise ValueError("Forecast surface job not found")
        task = job.get("task")
        if job["status"] in {"queued", "running"} and task:
            task.cancel()
            job["status"] = "cancelled"
        return self._snapshot(job)

    async def shutdown(self) -> None:
        tasks = [
            job["task"]
            for job in self._jobs.values()
            if job.get("task") and not job["task"].done()
        ]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def _prune(self) -> None:
        finished = [
            job
            for job in self._jobs.values()
            if job["status"]
            in {"complete", "insufficient_data", "cancelled", "failed"}
        ]
        for job in sorted(
            finished,
            key=lambda item: item["created_at"],
        )[:-20]:
            self._jobs.pop(job["job_id"], None)
            if self._key_to_job.get(job["request_key"]) == job["job_id"]:
                self._key_to_job.pop(job["request_key"], None)

    @staticmethod
    def _snapshot(job: dict) -> dict:
        return {
            key: value
            for key, value in job.items()
            if key not in {"task", "request_key"}
        }

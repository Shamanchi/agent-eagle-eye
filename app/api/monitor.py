"""Эндпоинты правил, метрик, алертов и дайджеста."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.services.watch import Alert, Rule, SeriesStats, Watcher, get_watcher

router = APIRouter()


class RuleRequest(BaseModel):
    metric: str = Field(min_length=1, max_length=64)
    op: Literal["gt", "lt"]
    threshold: float


class MetricRequest(BaseModel):
    metric: str = Field(min_length=1, max_length=64)
    value: float


class IngestResponse(BaseModel):
    metric: str
    value: float
    alerts: list[Alert]


def get_eye(settings: Settings = Depends(get_settings)) -> Watcher:
    return get_watcher(
        spike_window=settings.spike_window,
        spike_mult=settings.spike_mult,
        max_points=settings.max_points,
    )


@router.post("/rules", response_model=Rule)
async def add_rule(request: RuleRequest, eye: Watcher = Depends(get_eye)) -> Rule:
    try:
        return eye.add_rule(request.metric, request.op, request.threshold)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/rules", response_model=list[Rule])
async def rules(eye: Watcher = Depends(get_eye)) -> list[Rule]:
    return eye.rules()


@router.post("/metrics", response_model=IngestResponse)
async def ingest(request: MetricRequest, eye: Watcher = Depends(get_eye)) -> IngestResponse:
    try:
        fired = eye.ingest(request.metric, request.value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return IngestResponse(metric=request.metric.strip().lower(), value=request.value, alerts=fired)


@router.get("/metrics", response_model=SeriesStats)
async def metric_stats(name: str = "", eye: Watcher = Depends(get_eye)) -> SeriesStats:
    stats = eye.stats(name)
    if stats is None:
        raise HTTPException(status_code=404, detail=f"no data for {name!r}")
    return stats


@router.get("/alerts", response_model=list[Alert])
async def alerts(eye: Watcher = Depends(get_eye)) -> list[Alert]:
    return eye.alerts()


@router.get("/digest")
async def digest(eye: Watcher = Depends(get_eye)) -> dict:
    return {"digest_md": eye.digest()}

from datetime import date as date_type
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.orm import TraceOutcome
from app.models.schemas import TraceListResponse, TraceRead
from app.repositories.trace_repository import TraceRepository

router = APIRouter(tags=["traces"])

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


@router.get("/traces", response_model=TraceListResponse)
async def list_traces(
    endpoint: str | None = Query(default=None),
    outcome: TraceOutcome | None = Query(default=None),
    date: date_type | None = Query(
        default=None, description="Filter to traces created on this day."
    ),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
) -> TraceListResponse:
    traces, total = await TraceRepository(session).list_paginated(
        endpoint=endpoint, outcome=outcome, on_date=date, limit=limit, offset=offset
    )
    return TraceListResponse(
        items=[TraceRead.model_validate(trace) for trace in traces],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/traces/{trace_id}", response_model=TraceRead)
async def get_trace(trace_id: UUID, session: AsyncSession = Depends(get_db)) -> TraceRead:
    trace = await TraceRepository(session).get_by_id(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Trace not found.")
    return TraceRead.model_validate(trace)

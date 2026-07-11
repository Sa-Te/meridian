from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.orm import ActionItemStatus
from app.models.schemas import ActionItemRead
from app.repositories.action_item_repository import ActionItemRepository
from app.services.citations import build_citation

router = APIRouter(tags=["action-items"])


@router.get("/action-items", response_model=list[ActionItemRead])
async def list_action_items(
    status: ActionItemStatus | None = Query(default=None),
    owner: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
) -> list[ActionItemRead]:
    items = await ActionItemRepository(session).list(status=status, owner=owner)
    return [
        ActionItemRead(
            id=item.id,
            meeting_id=item.meeting_id,
            text=item.text,
            owner=item.owner,
            due_date=item.due_date,
            source_citation=build_citation(item.source_chunk),
            confidence=item.confidence,
            status=item.status,
            created_at=item.created_at,
        )
        for item in items
    ]

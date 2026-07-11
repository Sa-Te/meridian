from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.orm import ActionItemStatus
from app.models.schemas import ActionItemRead
from app.repositories.action_item_repository import ActionItemRepository

router = APIRouter(tags=["action-items"])


@router.get("/action-items", response_model=list[ActionItemRead])
async def list_action_items(
    status: ActionItemStatus | None = Query(default=None),
    owner: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
) -> list[ActionItemRead]:
    items = await ActionItemRepository(session).list(status=status, owner=owner)
    return [ActionItemRead.model_validate(item) for item in items]

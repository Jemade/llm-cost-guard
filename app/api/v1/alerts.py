from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.alert import AlertEvent
from app.schemas.alert import AlertEventResponse

router = APIRouter()


@router.get(
    "/alerts",
    response_model=List[AlertEventResponse],
    status_code=status.HTTP_200_OK,
    summary="List triggered budget alerts",
    description="Returns persisted alert events with deduplication details.",
)
async def list_alerts(
    scope: Optional[str] = Query(None, description="Filter by scope"),
    limit: int = Query(50, ge=1, le=200, description="Max records to return"),
    db: AsyncSession = Depends(get_db),
) -> List[AlertEventResponse]:
    stmt = select(AlertEvent).order_by(desc(AlertEvent.created_at)).limit(limit)
    if scope:
        stmt = stmt.where(AlertEvent.scope == scope)

    results = (await db.execute(stmt)).scalars().all()
    return [AlertEventResponse.model_validate(r) for r in results]

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.analytics_service import analytics_service

router = APIRouter(prefix="/analytics")


@router.get(
    "/summary",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Get overall spending and budget summary",
)
async def get_summary(
    scope: str = Query("global", description="Budget scope"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    return await analytics_service.get_summary(db, scope=scope)


@router.get(
    "/by-model",
    response_model=List[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Get spending and token usage breakdown by model",
)
async def get_by_model(
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    return await analytics_service.get_spend_by_model(db)


@router.get(
    "/by-endpoint",
    response_model=List[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Get spending breakdown by API endpoint",
)
async def get_by_endpoint(
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    return await analytics_service.get_spend_by_endpoint(db)


@router.get(
    "/timeseries",
    response_model=List[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Get daily spend and token timeseries",
)
async def get_timeseries(
    days: int = Query(14, ge=1, le=90, description="Number of past days"),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    return await analytics_service.get_timeseries(db, days=days)


@router.get(
    "/recent",
    response_model=List[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Get recent LLM usage requests",
)
async def get_recent(
    limit: int = Query(50, ge=1, le=200),
    user_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    return await analytics_service.get_recent_requests(db, limit=limit, user_id=user_id)

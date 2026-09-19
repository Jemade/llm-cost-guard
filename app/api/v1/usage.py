import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.usage import LLMUsageLog
from app.schemas.usage import UsageRecordCreate, UsageRecordResponse
from app.services.alert_service import alert_service
from app.services.budget_service import budget_service
from app.services.cost_calculator import cost_calculator
from app.services.pricing_catalog import pricing_catalog

router = APIRouter()


@router.post(
    "/usage",
    response_model=UsageRecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record actual LLM usage",
    description=(
        "Records actual token usage and latency after an LLM request completes. "
        "Separates estimated cost from actual cost without overwriting."
    ),
)
async def record_usage(
    payload: UsageRecordCreate,
    db: AsyncSession = Depends(get_db),
) -> UsageRecordResponse:
    # Compute total tokens if not provided
    total_tokens = payload.total_tokens or (payload.input_tokens + payload.output_tokens)

    # Compute actual cost if not explicitly provided and model is known
    actual_cost = payload.actual_cost
    if actual_cost is None:
        try:
            pricing = pricing_catalog.get(payload.provider, payload.model)
            _, _, computed_actual = cost_calculator.calculate(
                input_tokens=payload.input_tokens,
                output_tokens=payload.output_tokens,
                pricing=pricing,
            )
            actual_cost = computed_actual
        except Exception:
            actual_cost = payload.estimated_cost

    usage_record = LLMUsageLog(
        id=str(uuid.uuid4()),
        request_id=payload.request_id,
        user_id=payload.user_id,
        endpoint=payload.endpoint,
        provider=payload.provider,
        model=payload.model,
        input_tokens=payload.input_tokens,
        output_tokens=payload.output_tokens,
        total_tokens=total_tokens,
        estimated_cost=Decimal(str(payload.estimated_cost)),
        actual_cost=Decimal(str(actual_cost)) if actual_cost is not None else None,
        latency_ms=payload.latency_ms,
        status=payload.status.upper(),
        timestamp=payload.timestamp or datetime.now(timezone.utc),
        metadata_json=payload.metadata_json,
    )
    db.add(usage_record)
    await db.flush()

    # Commit in-flight reservation if one was held
    if payload.reservation_id:
        await budget_service.commit_reservation(db, payload.reservation_id)

    # Evaluate alerts on newly recorded spend
    periods = budget_service.get_period_starts()
    config = await budget_service.get_or_create_budget(db, scope="global")
    for period_type, period_start in periods.items():
        budget_limit = getattr(config, f"{period_type}_budget")
        if budget_limit is not None:
            spent = await budget_service.calculate_period_spend(db, "global", period_start)
            await alert_service.check_and_trigger_alerts(
                db=db,
                scope="global",
                period_type=period_type,
                period_start=period_start,
                spent=spent,
                budget=float(budget_limit),
                thresholds=config.alert_thresholds or [0.8, 0.9, 1.0],
            )

    return UsageRecordResponse.model_validate(usage_record)


@router.get(
    "/usage",
    response_model=List[UsageRecordResponse],
    status_code=status.HTTP_200_OK,
    summary="List recorded LLM usage logs",
    description="Retrieves historical usage logs with optional filters and pagination.",
)
async def list_usage(
    user_id: Optional[str] = Query(None, description="Filter by user or client ID"),
    endpoint: Optional[str] = Query(None, description="Filter by endpoint"),
    model: Optional[str] = Query(None, description="Filter by model name"),
    provider: Optional[str] = Query(None, description="Filter by provider"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (SUCCESS, FAILED, BLOCKED)"),
    limit: int = Query(50, ge=1, le=500, description="Number of records to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db),
) -> List[UsageRecordResponse]:
    stmt = select(LLMUsageLog).order_by(desc(LLMUsageLog.timestamp))

    if user_id:
        stmt = stmt.where(LLMUsageLog.user_id == user_id)
    if endpoint:
        stmt = stmt.where(LLMUsageLog.endpoint == endpoint)
    if model:
        stmt = stmt.where(LLMUsageLog.model == model)
    if provider:
        stmt = stmt.where(LLMUsageLog.provider == provider)
    if status_filter:
        stmt = stmt.where(LLMUsageLog.status == status_filter.upper())

    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    records = result.scalars().all()

    return [UsageRecordResponse.model_validate(r) for r in records]

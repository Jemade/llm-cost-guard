import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.budget import BudgetConfig
from app.schemas.budget import (
    BudgetConfigCreate,
    BudgetConfigResponse,
    BudgetPeriodStatus,
    BudgetStatusResponse,
)
from app.services.budget_service import budget_service

router = APIRouter()


@router.get(
    "/budgets",
    response_model=List[BudgetStatusResponse],
    status_code=status.HTTP_200_OK,
    summary="List budget statuses and spending",
    description="Retrieves all active budget scopes and their current daily, weekly, and monthly spending.",
)
async def list_budgets(
    scope: Optional[str] = Query(None, description="Optional scope to filter by"),
    db: AsyncSession = Depends(get_db),
) -> List[BudgetStatusResponse]:
    stmt = select(BudgetConfig)
    if scope:
        stmt = stmt.where(BudgetConfig.scope == scope)
    else:
        # Ensure at least 'global' budget exists
        await budget_service.get_or_create_budget(db, "global")

    configs = (await db.execute(stmt)).scalars().all()
    periods = budget_service.get_period_starts()

    responses: List[BudgetStatusResponse] = []
    for cfg in configs:
        period_data = {}
        for p_name, p_start in periods.items():
            limit = getattr(cfg, f"{p_name}_budget")
            budget_val = float(limit) if limit is not None else None
            spent = await budget_service.calculate_period_spend(db, cfg.scope, p_start)
            remaining = max(0.0, round(budget_val - spent, 4)) if budget_val is not None else None
            pct = round((spent / budget_val) * 100, 1) if budget_val and budget_val > 0 else None

            period_data[p_name] = BudgetPeriodStatus(
                budget=budget_val,
                spent=spent,
                remaining=remaining,
                percent_used=pct,
            )

        responses.append(
            BudgetStatusResponse(
                scope=cfg.scope,
                daily=period_data["daily"],
                weekly=period_data["weekly"],
                monthly=period_data["monthly"],
            )
        )

    return responses


@router.post(
    "/budgets",
    response_model=BudgetConfigResponse,
    status_code=status.HTTP_200_OK,
    summary="Create or update budget configuration",
    description="Sets or updates spending limits and alert thresholds for a specific scope.",
)
async def set_budget(
    payload: BudgetConfigCreate,
    db: AsyncSession = Depends(get_db),
) -> BudgetConfigResponse:
    stmt = select(BudgetConfig).where(BudgetConfig.scope == payload.scope)
    config = (await db.execute(stmt)).scalar_one_or_none()

    if not config:
        config = BudgetConfig(
            id=str(uuid.uuid4()),
            scope=payload.scope,
            daily_budget=Decimal(str(payload.daily_budget)) if payload.daily_budget is not None else None,
            weekly_budget=Decimal(str(payload.weekly_budget)) if payload.weekly_budget is not None else None,
            monthly_budget=Decimal(str(payload.monthly_budget)) if payload.monthly_budget is not None else None,
            alert_thresholds=payload.alert_thresholds,
            is_active=payload.is_active,
        )
        db.add(config)
    else:
        config.daily_budget = Decimal(str(payload.daily_budget)) if payload.daily_budget is not None else None
        config.weekly_budget = Decimal(str(payload.weekly_budget)) if payload.weekly_budget is not None else None
        config.monthly_budget = Decimal(str(payload.monthly_budget)) if payload.monthly_budget is not None else None
        config.alert_thresholds = payload.alert_thresholds
        config.is_active = payload.is_active
        config.updated_at = datetime.now(timezone.utc)

    await db.flush()
    return BudgetConfigResponse.model_validate(config)

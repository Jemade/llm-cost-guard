import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.budget import BudgetConfig, BudgetReservation
from app.models.usage import LLMUsageLog
from app.schemas.cost_check import PeriodBudgetDetail
from app.services.alert_service import alert_service


class BudgetService:
    """
    Evaluates spending against daily, weekly, and monthly budgets.
    Enforces concurrency-safe budget checks via row locking and reservation tracking.
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    def get_period_starts(self, ref_time: Optional[datetime] = None) -> Dict[str, datetime]:
        """
        Calculates UTC start timestamps for daily, weekly, and monthly periods.
        """
        now = ref_time or datetime.now(timezone.utc)
        # Naive timestamps are treated as UTC; aware values are converted before
        # taking calendar boundaries so local dates cannot shift UTC budgets.
        now = now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now.astimezone(timezone.utc)
        daily_start = datetime(now.year, now.month, now.day, 0, 0, 0, tzinfo=timezone.utc)
        weekly_start = daily_start - timedelta(days=daily_start.weekday())
        monthly_start = datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=timezone.utc)
        return {
            "daily": daily_start,
            "weekly": weekly_start,
            "monthly": monthly_start,
        }

    async def get_or_create_budget(
        self, db: AsyncSession, scope: str = "global", for_update: bool = False
    ) -> BudgetConfig:
        """
        Fetches budget configuration for the given scope, creating a default one if none exists.
        Optionally applies row-level lock (FOR UPDATE) for transactional concurrency safety.
        """
        stmt = select(BudgetConfig).where(BudgetConfig.scope == scope)
        if for_update and not db.get_bind().dialect.name.startswith("sqlite"):
            stmt = stmt.with_for_update()

        result = await db.execute(stmt)
        config = result.scalar_one_or_none()

        if not config:
            config = BudgetConfig(
                id=str(uuid.uuid4()),
                scope=scope,
                daily_budget=Decimal(str(self.settings.DEFAULT_DAILY_BUDGET)),
                weekly_budget=Decimal(str(self.settings.DEFAULT_WEEKLY_BUDGET)),
                monthly_budget=Decimal(str(self.settings.DEFAULT_MONTHLY_BUDGET)),
                alert_thresholds=self.settings.DEFAULT_ALERT_THRESHOLDS,
                is_active=True,
            )
            db.add(config)
            await db.flush()

        return config

    async def calculate_period_spend(
        self, db: AsyncSession, scope: str, start_time: datetime
    ) -> float:
        """
        Calculates total spend since start_time including:
        1. Recorded usage (COALESCE actual_cost, estimated_cost)
        2. Active unexpired reservations (PENDING status with expires_at > now)
        """
        now = datetime.now(timezone.utc)

        # 1. Sum recorded non-blocked usage
        usage_stmt = select(
            func.coalesce(
                func.sum(
                    func.coalesce(LLMUsageLog.actual_cost, LLMUsageLog.estimated_cost)
                ),
                0.0,
            )
        ).where(
            LLMUsageLog.timestamp >= start_time,
            LLMUsageLog.status != "BLOCKED",
        )
        if scope != "global":
            # If scoped to user or endpoint
            if scope.startswith("user:"):
                user_id = scope.split("user:", 1)[1]
                usage_stmt = usage_stmt.where(LLMUsageLog.user_id == user_id)
            elif scope.startswith("endpoint:"):
                endpoint = scope.split("endpoint:", 1)[1]
                usage_stmt = usage_stmt.where(LLMUsageLog.endpoint == endpoint)

        usage_result = await db.execute(usage_stmt)
        usage_spent = float(usage_result.scalar_one())

        # 2. Sum active in-flight reservations
        res_stmt = select(
            func.coalesce(func.sum(BudgetReservation.estimated_cost), 0.0)
        ).where(
            BudgetReservation.scope == scope,
            BudgetReservation.status == "PENDING",
            BudgetReservation.expires_at > now,
        )
        res_result = await db.execute(res_stmt)
        reservation_spent = float(res_result.scalar_one())

        return round(usage_spent + reservation_spent, 6)

    async def check_budget(
        self,
        db: AsyncSession,
        estimated_cost: float,
        scope: str = "global",
        reserve: bool = False,
        request_id: Optional[str] = None,
    ) -> Tuple[str, str, Dict[str, PeriodBudgetDetail], Optional[str]]:
        """
        Evaluates estimated_cost against daily, weekly, and monthly limits.
        Returns:
            (decision, reason, period_details, reservation_id)
        """
        # Fetch budget config with row-level lock if available
        config = await self.get_or_create_budget(db, scope=scope, for_update=True)

        if not config.is_active:
            # Inactive budget configuration allows all requests
            empty_detail = PeriodBudgetDetail(budget=None, spent=0.0, remaining=None, exceeded=False)
            return "ALLOW", "BUDGET_INACTIVE", {"daily": empty_detail, "weekly": empty_detail, "monthly": empty_detail}, None

        periods = self.get_period_starts()
        period_details: Dict[str, PeriodBudgetDetail] = {}
        decision = "ALLOW"
        reason = "WITHIN_BUDGET"

        limits = {
            "daily": float(config.daily_budget) if config.daily_budget is not None else None,
            "weekly": float(config.weekly_budget) if config.weekly_budget is not None else None,
            "monthly": float(config.monthly_budget) if config.monthly_budget is not None else None,
        }

        for period_type, period_start in periods.items():
            budget = limits[period_type]
            spent = await self.calculate_period_spend(db, scope, period_start)

            # Check threshold alerts for current spend
            if budget is not None:
                await alert_service.check_and_trigger_alerts(
                    db=db,
                    scope=scope,
                    period_type=period_type,
                    period_start=period_start,
                    spent=spent,
                    budget=budget,
                    thresholds=config.alert_thresholds or self.settings.DEFAULT_ALERT_THRESHOLDS,
                )

            if budget is not None:
                remaining = max(0.0, round(budget - spent, 6))
                exceeded = (spent + estimated_cost) > budget

                if budget == 0.0:
                    decision = "BLOCK"
                    reason = "ZERO_BUDGET_CONFIGURED"
                    exceeded = True
                elif exceeded and decision == "ALLOW":
                    decision = "BLOCK"
                    reason = f"REQUEST_EXCEEDS_{period_type.upper()}_BUDGET"

                period_details[period_type] = PeriodBudgetDetail(
                    budget=budget,
                    spent=spent,
                    remaining=remaining,
                    exceeded=exceeded,
                )
            else:
                period_details[period_type] = PeriodBudgetDetail(
                    budget=None,
                    spent=spent,
                    remaining=None,
                    exceeded=False,
                )

        reservation_id: Optional[str] = None
        if decision == "ALLOW" and reserve:
            reservation_id = str(uuid.uuid4())
            expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=self.settings.RESERVATION_TTL_SECONDS
            )
            reservation = BudgetReservation(
                id=reservation_id,
                scope=scope,
                request_id=request_id or reservation_id,
                estimated_cost=Decimal(str(estimated_cost)),
                status="PENDING",
                expires_at=expires_at,
            )
            db.add(reservation)
            await db.flush()

        return decision, reason, period_details, reservation_id

    async def commit_reservation(
        self, db: AsyncSession, reservation_id: str
    ) -> None:
        """Marks an in-flight reservation as COMMITTED once actual usage is recorded."""
        stmt = select(BudgetReservation).where(BudgetReservation.id == reservation_id)
        result = await db.execute(stmt)
        res = result.scalar_one_or_none()
        if res:
            res.status = "COMMITTED"
            await db.flush()

    async def release_reservation(
        self, db: AsyncSession, reservation_id: str
    ) -> None:
        """Releases a reservation if the LLM request was cancelled or failed before execution."""
        stmt = select(BudgetReservation).where(BudgetReservation.id == reservation_id)
        result = await db.execute(stmt)
        res = result.scalar_one_or_none()
        if res:
            res.status = "RELEASED"
            await db.flush()


budget_service = BudgetService()

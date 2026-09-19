from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import case, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usage import LLMUsageLog
from app.services.budget_service import budget_service


class AnalyticsService:
    """
    Computes spend aggregations, token consumption, and budget metrics
    from actual database records for reporting and dashboard views.
    """

    async def get_summary(self, db: AsyncSession, scope: str = "global") -> Dict[str, Any]:
        periods = budget_service.get_period_starts()
        config = await budget_service.get_or_create_budget(db, scope=scope)

        daily_spent = await budget_service.calculate_period_spend(db, scope, periods["daily"])
        weekly_spent = await budget_service.calculate_period_spend(db, scope, periods["weekly"])
        monthly_spent = await budget_service.calculate_period_spend(db, scope, periods["monthly"])

        # Overall totals
        total_stmt = select(
            func.coalesce(
                func.sum(
                    case(
                        (LLMUsageLog.status != "BLOCKED", func.coalesce(LLMUsageLog.actual_cost, LLMUsageLog.estimated_cost)),
                        else_=0.0,
                    )
                ),
                0.0,
            ).label("total_spent"),
            func.coalesce(func.sum(LLMUsageLog.input_tokens), 0).label("total_input_tokens"),
            func.coalesce(func.sum(LLMUsageLog.output_tokens), 0).label("total_output_tokens"),
            func.coalesce(func.sum(LLMUsageLog.total_tokens), 0).label("total_tokens"),
            func.count(LLMUsageLog.id).label("total_requests"),
            func.coalesce(func.sum(case((LLMUsageLog.status == "SUCCESS", 1), else_=0)), 0).label("successful_requests"),
            func.coalesce(func.sum(case((LLMUsageLog.status == "BLOCKED", 1), else_=0)), 0).label("blocked_requests"),
            func.coalesce(func.sum(case((LLMUsageLog.status == "FAILED", 1), else_=0)), 0).label("failed_requests"),
        )
        total_res = (await db.execute(total_stmt)).one()

        daily_budget = float(config.daily_budget) if config.daily_budget is not None else None
        weekly_budget = float(config.weekly_budget) if config.weekly_budget is not None else None
        monthly_budget = float(config.monthly_budget) if config.monthly_budget is not None else None

        return {
            "scope": scope,
            "total_spend": round(float(total_res.total_spent), 4),
            "daily_spend": round(daily_spent, 4),
            "weekly_spend": round(weekly_spent, 4),
            "monthly_spend": round(monthly_spent, 4),
            "daily_budget": daily_budget,
            "weekly_budget": weekly_budget,
            "monthly_budget": monthly_budget,
            "daily_remaining": max(0.0, round(daily_budget - daily_spent, 4)) if daily_budget is not None else None,
            "weekly_remaining": max(0.0, round(weekly_budget - weekly_spent, 4)) if weekly_budget is not None else None,
            "monthly_remaining": max(0.0, round(monthly_budget - monthly_spent, 4)) if monthly_budget is not None else None,
            "daily_percent_used": round((daily_spent / daily_budget) * 100, 1) if daily_budget and daily_budget > 0 else 0.0,
            "weekly_percent_used": round((weekly_spent / weekly_budget) * 100, 1) if weekly_budget and weekly_budget > 0 else 0.0,
            "monthly_percent_used": round((monthly_spent / monthly_budget) * 100, 1) if monthly_budget and monthly_budget > 0 else 0.0,
            "tokens": {
                "input": int(total_res.total_input_tokens),
                "output": int(total_res.total_output_tokens),
                "total": int(total_res.total_tokens),
            },
            "requests": {
                "total": int(total_res.total_requests),
                "successful": int(total_res.successful_requests),
                "blocked": int(total_res.blocked_requests),
                "failed": int(total_res.failed_requests),
            },
        }

    async def get_spend_by_model(self, db: AsyncSession) -> List[Dict[str, Any]]:
        stmt = (
            select(
                LLMUsageLog.model,
                LLMUsageLog.provider,
                func.coalesce(
                    func.sum(
                        case(
                            (LLMUsageLog.status != "BLOCKED", func.coalesce(LLMUsageLog.actual_cost, LLMUsageLog.estimated_cost)),
                            else_=0.0,
                        )
                    ),
                    0.0,
                ).label("spend"),
                func.coalesce(func.sum(LLMUsageLog.input_tokens), 0).label("input_tokens"),
                func.coalesce(func.sum(LLMUsageLog.output_tokens), 0).label("output_tokens"),
                func.coalesce(func.sum(LLMUsageLog.total_tokens), 0).label("total_tokens"),
                func.count(LLMUsageLog.id).label("requests"),
            )
            .group_by(LLMUsageLog.model, LLMUsageLog.provider)
            .order_by(desc("spend"))
        )
        results = (await db.execute(stmt)).all()

        total_spend = sum(float(r.spend) for r in results) or 1.0

        return [
            {
                "model": r.model,
                "provider": r.provider,
                "spend": round(float(r.spend), 4),
                "spend_percent": round((float(r.spend) / total_spend) * 100, 1),
                "input_tokens": int(r.input_tokens),
                "output_tokens": int(r.output_tokens),
                "total_tokens": int(r.total_tokens),
                "requests": int(r.requests),
            }
            for r in results
        ]

    async def get_spend_by_endpoint(self, db: AsyncSession) -> List[Dict[str, Any]]:
        stmt = (
            select(
                LLMUsageLog.endpoint,
                func.coalesce(
                    func.sum(
                        case(
                            (LLMUsageLog.status != "BLOCKED", func.coalesce(LLMUsageLog.actual_cost, LLMUsageLog.estimated_cost)),
                            else_=0.0,
                        )
                    ),
                    0.0,
                ).label("spend"),
                func.coalesce(func.sum(LLMUsageLog.total_tokens), 0).label("total_tokens"),
                func.count(LLMUsageLog.id).label("requests"),
            )
            .group_by(LLMUsageLog.endpoint)
            .order_by(desc("spend"))
        )
        results = (await db.execute(stmt)).all()

        total_spend = sum(float(r.spend) for r in results) or 1.0

        return [
            {
                "endpoint": r.endpoint,
                "spend": round(float(r.spend), 4),
                "spend_percent": round((float(r.spend) / total_spend) * 100, 1),
                "total_tokens": int(r.total_tokens),
                "requests": int(r.requests),
            }
            for r in results
        ]

    async def get_timeseries(self, db: AsyncSession, days: int = 14) -> List[Dict[str, Any]]:
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = (
            select(
                func.date(LLMUsageLog.timestamp).label("date"),
                func.coalesce(
                    func.sum(
                        case(
                            (LLMUsageLog.status != "BLOCKED", func.coalesce(LLMUsageLog.actual_cost, LLMUsageLog.estimated_cost)),
                            else_=0.0,
                        )
                    ),
                    0.0,
                ).label("spend"),
                func.coalesce(func.sum(LLMUsageLog.total_tokens), 0).label("tokens"),
                func.count(LLMUsageLog.id).label("requests"),
            )
            .where(LLMUsageLog.timestamp >= start_date)
            .group_by(func.date(LLMUsageLog.timestamp))
            .order_by("date")
        )
        results = (await db.execute(stmt)).all()

        return [
            {
                "date": str(r.date),
                "spend": round(float(r.spend), 4),
                "tokens": int(r.tokens),
                "requests": int(r.requests),
            }
            for r in results
        ]

    async def get_recent_requests(
        self, db: AsyncSession, limit: int = 50, user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        stmt = select(LLMUsageLog).order_by(desc(LLMUsageLog.timestamp)).limit(limit)
        if user_id:
            stmt = stmt.where(LLMUsageLog.user_id == user_id)
        results = (await db.execute(stmt)).scalars().all()

        return [
            {
                "id": r.id,
                "request_id": r.request_id,
                "user_id": r.user_id,
                "endpoint": r.endpoint,
                "provider": r.provider,
                "model": r.model,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "total_tokens": r.total_tokens,
                "estimated_cost": float(r.estimated_cost),
                "actual_cost": float(r.actual_cost) if r.actual_cost is not None else None,
                "latency_ms": r.latency_ms,
                "status": r.status,
                "timestamp": r.timestamp.isoformat(),
            }
            for r in results
        ]


analytics_service = AnalyticsService()

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.analytics_service import analytics_service
from app.services.pricing_catalog import pricing_catalog

router = APIRouter()


@router.get(
    "/metrics",
    status_code=status.HTTP_200_OK,
    summary="System and operational metrics",
    description="Returns JSON-formatted metrics for Prometheus scrapers or monitoring dashboards.",
)
async def get_metrics(db: AsyncSession = Depends(get_db)):
    summary = await analytics_service.get_summary(db)
    models = await analytics_service.get_spend_by_model(db)

    return {
        "costguard_total_spend_usd": summary["total_spend"],
        "costguard_daily_spend_usd": summary["daily_spend"],
        "costguard_weekly_spend_usd": summary["weekly_spend"],
        "costguard_monthly_spend_usd": summary["monthly_spend"],
        "costguard_daily_remaining_usd": summary["daily_remaining"],
        "costguard_weekly_remaining_usd": summary["weekly_remaining"],
        "costguard_monthly_remaining_usd": summary["monthly_remaining"],
        "costguard_requests_total": summary["requests"]["total"],
        "costguard_requests_successful": summary["requests"]["successful"],
        "costguard_requests_blocked": summary["requests"]["blocked"],
        "costguard_requests_failed": summary["requests"]["failed"],
        "costguard_tokens_input_total": summary["tokens"]["input"],
        "costguard_tokens_output_total": summary["tokens"]["output"],
        "costguard_tokens_total": summary["tokens"]["total"],
        "costguard_pricing_catalog_version": pricing_catalog.version,
        "costguard_models_configured_count": len(pricing_catalog.list_models()),
        "costguard_models_active_count": len(models),
    }

from fastapi import APIRouter

from app.api.v1.alerts import router as alerts_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.budgets import router as budgets_router
from app.api.v1.cost_check import router as cost_check_router
from app.api.v1.estimate import router as estimate_router
from app.api.v1.usage import router as usage_router

router = APIRouter(prefix="/v1")

router.include_router(estimate_router, tags=["Estimation"])
router.include_router(cost_check_router, tags=["Cost & Budget Control"])
router.include_router(usage_router, tags=["Usage Tracking"])
router.include_router(budgets_router, tags=["Budgets"])
router.include_router(alerts_router, tags=["Alerts"])
router.include_router(analytics_router, tags=["Analytics"])

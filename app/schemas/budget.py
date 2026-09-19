from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class BudgetConfigCreate(BaseModel):
    scope: str = Field(
        default="global",
        description="Scope identifier, e.g. 'global', 'user:team_alpha', or 'endpoint:/v1/chat'.",
    )
    daily_budget: Optional[float] = Field(None, ge=0.0, description="Daily spend limit in USD.")
    weekly_budget: Optional[float] = Field(None, ge=0.0, description="Weekly spend limit in USD.")
    monthly_budget: Optional[float] = Field(None, ge=0.0, description="Monthly spend limit in USD.")
    alert_thresholds: List[float] = Field(
        default_factory=lambda: [0.80, 0.90, 1.00],
        description="List of percentage thresholds (0.0 to 1.0) to trigger alerts.",
    )
    is_active: bool = True


class BudgetConfigResponse(BaseModel):
    id: str
    scope: str
    daily_budget: Optional[float]
    weekly_budget: Optional[float]
    monthly_budget: Optional[float]
    alert_thresholds: List[float]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BudgetPeriodStatus(BaseModel):
    budget: Optional[float]
    spent: float
    remaining: Optional[float]
    percent_used: Optional[float]


class BudgetStatusResponse(BaseModel):
    scope: str
    daily: BudgetPeriodStatus
    weekly: BudgetPeriodStatus
    monthly: BudgetPeriodStatus

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict


class AlertEventResponse(BaseModel):
    id: str
    scope: str
    period_type: str
    period_start: datetime
    threshold: float
    spent_amount: float
    budget_amount: float
    channel: str
    status: str
    payload: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

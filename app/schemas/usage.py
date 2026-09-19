from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class UsageRecordCreate(BaseModel):
    request_id: str = Field(..., description="Unique ID for the LLM request.")
    user_id: str = Field(..., description="User or client who initiated the request.")
    endpoint: str = Field(default="/v1/chat/completions", description="Endpoint invoked.")
    provider: str = Field(..., description="LLM provider name.")
    model: str = Field(..., description="Model name used.")
    input_tokens: int = Field(..., ge=0)
    output_tokens: int = Field(..., ge=0)
    total_tokens: Optional[int] = Field(None, ge=0)
    estimated_cost: float = Field(..., ge=0.0)
    actual_cost: Optional[float] = Field(None, ge=0.0)
    latency_ms: float = Field(default=0.0, ge=0.0)
    status: str = Field(default="SUCCESS", description="SUCCESS, FAILED, or BLOCKED.")
    timestamp: Optional[datetime] = None
    metadata_json: Optional[Dict[str, Any]] = None
    reservation_id: Optional[str] = Field(
        None, description="Optional reservation ID to commit/release."
    )


class UsageRecordResponse(BaseModel):
    id: str
    request_id: str
    user_id: str
    endpoint: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost: float
    actual_cost: Optional[float]
    latency_ms: float
    status: str
    timestamp: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

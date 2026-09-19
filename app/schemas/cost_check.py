from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class CostCheckRequest(BaseModel):
    provider: str = Field(..., description="LLM provider name, e.g. 'openai', 'anthropic'.")
    model: str = Field(..., description="Model identifier, e.g. 'gpt-4o'.")
    prompt: Optional[str] = Field(None, description="Prompt string.")
    messages: Optional[List[Dict[str, Any]]] = Field(None, description="Chat messages array.")
    expected_output_tokens: int = Field(default=0, ge=0)
    user_id: str = Field(default="default_user", description="User or client identifier.")
    endpoint: str = Field(default="/v1/chat/completions", description="Target API endpoint.")
    request_id: Optional[str] = Field(None, description="Optional caller request ID for tracing.")
    reserve: bool = Field(
        default=False,
        description="If True, places an atomic reservation on the budget to prevent concurrent overruns.",
    )

    @model_validator(mode="after")
    def check_input_present(self) -> "CostCheckRequest":
        if not self.prompt and not self.messages:
            raise ValueError("Either 'prompt' or 'messages' must be provided.")
        return self


class PeriodBudgetDetail(BaseModel):
    budget: Optional[float]
    spent: float
    remaining: Optional[float]
    exceeded: bool


class CostCheckResponse(BaseModel):
    decision: str = Field(..., description="'ALLOW' or 'BLOCK'.")
    reason: str = Field(..., description="Explanation for decision, e.g. 'WITHIN_BUDGET' or 'REQUEST_EXCEEDS_DAILY_BUDGET'.")
    estimated_cost: float
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_total_tokens: int
    daily: PeriodBudgetDetail
    weekly: PeriodBudgetDetail
    monthly: PeriodBudgetDetail
    reservation_id: Optional[str] = Field(
        None, description="Reservation ID if reserve=True and request was allowed."
    )

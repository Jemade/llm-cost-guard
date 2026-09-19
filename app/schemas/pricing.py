from typing import List, Optional

from pydantic import BaseModel, Field


class ModelPricingSchema(BaseModel):
    provider: str
    model: str
    display_name: Optional[str] = None
    tokenizer_type: str = Field(
        default="tiktoken",
        description="Tokenizer type: 'tiktoken' (exact for OpenAI) or 'approximation' (Anthropic/Gemini/DeepSeek).",
    )
    encoding_name: Optional[str] = None
    input_cost_per_1m_tokens: float = Field(..., ge=0.0)
    output_cost_per_1m_tokens: float = Field(..., ge=0.0)
    currency: str = "USD"
    effective_date: str
    last_verified: str
    notes: Optional[str] = None


class PricingCatalogSchema(BaseModel):
    version: str
    currency: str = "USD"
    models: List[ModelPricingSchema]

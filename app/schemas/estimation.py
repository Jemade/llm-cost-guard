from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class MessageItem(BaseModel):
    role: str = Field(..., description="Role of the message sender, e.g. 'system', 'user', 'assistant'.")
    content: str = Field(..., description="Text content of the message.")


class EstimateRequest(BaseModel):
    provider: str = Field(..., description="LLM provider name, e.g. 'openai', 'anthropic', 'google', 'deepseek'.")
    model: str = Field(..., description="Model identifier, e.g. 'gpt-4o', 'claude-3-5-sonnet'.")
    prompt: Optional[str] = Field(None, description="Plain text prompt string.")
    messages: Optional[List[Dict[str, Any]]] = Field(
        None, description="List of chat message objects (e.g. [{'role': 'user', 'content': '...'}])"
    )
    expected_output_tokens: int = Field(
        default=0,
        ge=0,
        description="Estimated or max tokens expected in the model response.",
    )

    @model_validator(mode="after")
    def check_input_present(self) -> "EstimateRequest":
        if not self.prompt and not self.messages:
            raise ValueError("Either 'prompt' or 'messages' must be provided.")
        return self


class EstimateResponse(BaseModel):
    provider: str
    model: str
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_total_tokens: int
    estimated_input_cost: float
    estimated_output_cost: float
    estimated_total_cost: float
    currency: str = "USD"
    tokenizer_type: str
    confidence: str = Field(
        description="'exact' when using official model tokenizer (e.g. tiktoken for OpenAI), 'approximation' when calibrated heuristic is used."
    )
    tokenizer_note: Optional[str] = None

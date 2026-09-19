from fastapi import APIRouter, HTTPException, status

from app.core.exceptions import ModelPricingNotFoundError
from app.schemas.estimation import EstimateRequest, EstimateResponse
from app.services.cost_calculator import cost_calculator
from app.services.pricing_catalog import pricing_catalog
from app.services.token_estimator import token_estimator

router = APIRouter()


@router.post(
    "/estimate",
    response_model=EstimateResponse,
    status_code=status.HTTP_200_OK,
    summary="Estimate pre-flight tokens and cost",
    description=(
        "Calculates estimated input tokens, output tokens, and precise USD cost "
        "based on prompt or chat messages and expected output tokens, without calling the LLM."
    ),
)
async def estimate_cost(request: EstimateRequest) -> EstimateResponse:
    try:
        pricing = pricing_catalog.get(request.provider, request.model)
    except ModelPricingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    (
        input_tokens,
        tokenizer_type,
        confidence,
        note,
    ) = token_estimator.estimate_input_tokens(
        pricing=pricing,
        prompt=request.prompt,
        messages=request.messages,
    )

    output_tokens = request.expected_output_tokens
    total_tokens = input_tokens + output_tokens

    input_cost, output_cost, total_cost = cost_calculator.calculate(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        pricing=pricing,
    )

    return EstimateResponse(
        provider=request.provider,
        model=request.model,
        estimated_input_tokens=input_tokens,
        estimated_output_tokens=output_tokens,
        estimated_total_tokens=total_tokens,
        estimated_input_cost=input_cost,
        estimated_output_cost=output_cost,
        estimated_total_cost=total_cost,
        currency=pricing.currency,
        tokenizer_type=tokenizer_type,
        confidence=confidence,
        tokenizer_note=note,
    )

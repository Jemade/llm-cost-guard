from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import ModelPricingNotFoundError
from app.schemas.cost_check import CostCheckRequest, CostCheckResponse
from app.services.budget_service import budget_service
from app.services.cost_calculator import cost_calculator
from app.services.pricing_catalog import pricing_catalog
from app.services.token_estimator import token_estimator

router = APIRouter()


@router.post(
    "/cost/check",
    response_model=CostCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Pre-flight budget check & dry-run blocking",
    description=(
        "Evaluates whether a planned LLM request is permitted under daily, weekly, "
        "and monthly budget limits. Returns ALLOW or BLOCK before calling the provider."
    ),
)
@router.post(
    "/generate/check",
    response_model=CostCheckResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def check_cost(
    request: CostCheckRequest,
    db: AsyncSession = Depends(get_db),
) -> CostCheckResponse:
    try:
        pricing = pricing_catalog.get(request.provider, request.model)
    except ModelPricingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    (
        input_tokens,
        _,
        _,
        _,
    ) = token_estimator.estimate_input_tokens(
        pricing=pricing,
        prompt=request.prompt,
        messages=request.messages,
    )

    output_tokens = request.expected_output_tokens
    total_tokens = input_tokens + output_tokens

    _, _, total_cost = cost_calculator.calculate(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        pricing=pricing,
    )

    # Check user-specific scope first if configured, else global scope
    scope = f"user:{request.user_id}" if request.user_id != "default_user" else "global"

    decision, reason, periods, reservation_id = await budget_service.check_budget(
        db=db,
        estimated_cost=total_cost,
        scope=scope,
        reserve=request.reserve,
        request_id=request.request_id,
    )

    return CostCheckResponse(
        decision=decision,
        reason=reason,
        estimated_cost=total_cost,
        estimated_input_tokens=input_tokens,
        estimated_output_tokens=output_tokens,
        estimated_total_tokens=total_tokens,
        daily=periods["daily"],
        weekly=periods["weekly"],
        monthly=periods["monthly"],
        reservation_id=reservation_id,
    )

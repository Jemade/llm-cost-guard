import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usage import LLMUsageLog
from app.services.budget_service import budget_service


@pytest.mark.asyncio
async def test_budget_within_limit_allowed(test_db_session: AsyncSession):
    # Set daily budget of $5.00
    config = await budget_service.get_or_create_budget(test_db_session, scope="global")
    config.daily_budget = Decimal("5.00")
    await test_db_session.flush()

    decision, reason, periods, _ = await budget_service.check_budget(
        db=test_db_session,
        estimated_cost=0.50,
        scope="global",
    )
    assert decision == "ALLOW"
    assert reason == "WITHIN_BUDGET"
    assert periods["daily"].remaining == 5.00
    assert not periods["daily"].exceeded


@pytest.mark.asyncio
async def test_budget_exceeded_blocked(test_db_session: AsyncSession):
    # Set daily budget of $1.00 and add $0.90 prior spend
    config = await budget_service.get_or_create_budget(test_db_session, scope="global")
    config.daily_budget = Decimal("1.00")
    await test_db_session.flush()

    prior_log = LLMUsageLog(
        id=str(uuid.uuid4()),
        request_id="req_prior",
        user_id="user_test",
        endpoint="/v1/chat",
        provider="openai",
        model="gpt-4o",
        input_tokens=1000,
        output_tokens=1000,
        total_tokens=2000,
        estimated_cost=Decimal("0.90"),
        actual_cost=Decimal("0.90"),
        status="SUCCESS",
        timestamp=datetime.now(timezone.utc),
    )
    test_db_session.add(prior_log)
    await test_db_session.flush()

    # Request of $0.20 when remaining is $0.10 should be BLOCKED
    decision, reason, periods, _ = await budget_service.check_budget(
        db=test_db_session,
        estimated_cost=0.20,
        scope="global",
    )
    assert decision == "BLOCK"
    assert reason == "REQUEST_EXCEEDS_DAILY_BUDGET"
    assert periods["daily"].exceeded is True
    assert periods["daily"].remaining == 0.10


@pytest.mark.asyncio
async def test_budget_zero_is_blocked(test_db_session: AsyncSession):
    config = await budget_service.get_or_create_budget(test_db_session, scope="user:zero_user")
    config.daily_budget = Decimal("0.00")
    await test_db_session.flush()

    decision, reason, _, _ = await budget_service.check_budget(
        db=test_db_session,
        estimated_cost=0.01,
        scope="user:zero_user",
    )
    assert decision == "BLOCK"
    assert reason == "ZERO_BUDGET_CONFIGURED"


@pytest.mark.asyncio
async def test_budget_exact_match_allowed(test_db_session: AsyncSession):
    config = await budget_service.get_or_create_budget(test_db_session, scope="user:exact_user")
    config.daily_budget = Decimal("2.50")
    await test_db_session.flush()

    decision, reason, _, _ = await budget_service.check_budget(
        db=test_db_session,
        estimated_cost=2.50,
        scope="user:exact_user",
    )
    assert decision == "ALLOW"
    assert reason == "WITHIN_BUDGET"


@pytest.mark.asyncio
async def test_inactive_budget_allows(test_db_session: AsyncSession):
    config = await budget_service.get_or_create_budget(test_db_session, scope="user:inactive_user")
    config.daily_budget = Decimal("0.10")
    config.is_active = False
    await test_db_session.flush()

    decision, reason, _, _ = await budget_service.check_budget(
        db=test_db_session,
        estimated_cost=100.0,
        scope="user:inactive_user",
    )
    assert decision == "ALLOW"
    assert reason == "BUDGET_INACTIVE"


def test_period_boundaries_convert_to_utc():
    from datetime import timedelta

    local_time = datetime(2026, 10, 1, 1, tzinfo=timezone(timedelta(hours=2)))
    periods = budget_service.get_period_starts(local_time)
    assert periods["daily"] == datetime(2026, 9, 30, tzinfo=timezone.utc)
    assert periods["monthly"] == datetime(2026, 9, 1, tzinfo=timezone.utc)
    assert periods["weekly"] == datetime(2026, 9, 28, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_pending_reservation_counts_across_period_boundary(test_db_session):
    from datetime import timedelta

    from app.models.budget import BudgetReservation

    now = datetime.now(timezone.utc)
    start = budget_service.get_period_starts(now)["daily"]
    test_db_session.add(BudgetReservation(
        id=str(uuid.uuid4()), scope="global", request_id="rollover",
        estimated_cost=Decimal("0.75"), status="PENDING",
        created_at=start - timedelta(seconds=1), expires_at=now + timedelta(minutes=5),
    ))
    await test_db_session.flush()
    assert await budget_service.calculate_period_spend(test_db_session, "global", start) == 0.75

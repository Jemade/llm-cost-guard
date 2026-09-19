from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.budget_service import budget_service


@pytest.mark.asyncio
async def test_concurrent_reservations_prevent_overspend(test_db_session: AsyncSession):
    """
    Tests that when two requests each needing $0.40 arrive concurrently against
    a $0.60 remaining budget, the first places a reservation and is ALLOWED,
    while the second detects the active reservation and is BLOCKED.
    """
    scope = "user:concurrency_test"
    config = await budget_service.get_or_create_budget(test_db_session, scope=scope)
    config.daily_budget = Decimal("0.60")
    await test_db_session.flush()

    # Request 1 arrives, costs $0.40, with reserve=True
    decision1, reason1, _, res_id1 = await budget_service.check_budget(
        db=test_db_session,
        estimated_cost=0.40,
        scope=scope,
        reserve=True,
    )
    assert decision1 == "ALLOW"
    assert reason1 == "WITHIN_BUDGET"
    assert res_id1 is not None

    # Request 2 arrives immediately after, costs $0.40, before Request 1 finishes
    decision2, reason2, periods2, res_id2 = await budget_service.check_budget(
        db=test_db_session,
        estimated_cost=0.40,
        scope=scope,
        reserve=True,
    )
    # Total would be $0.40 (reserved) + $0.40 (new) = $0.80 > $0.60
    assert decision2 == "BLOCK"
    assert reason2 == "REQUEST_EXCEEDS_DAILY_BUDGET"
    assert res_id2 is None

    # Request 1 is committed
    await budget_service.commit_reservation(test_db_session, res_id1)

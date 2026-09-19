from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import AlertEvent
from app.services.alert_service import alert_service


@pytest.mark.asyncio
async def test_threshold_alerts_and_deduplication(test_db_session: AsyncSession):
    scope = "test_alert_scope"
    period_type = "daily"
    period_start = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    budget = 100.0
    thresholds = [0.80, 0.90, 1.00]

    # Spend is $85 (85% > 80%)
    events = await alert_service.check_and_trigger_alerts(
        db=test_db_session,
        scope=scope,
        period_type=period_type,
        period_start=period_start,
        spent=85.0,
        budget=budget,
        thresholds=thresholds,
    )
    # Only 80% threshold should trigger
    assert len(events) == 1
    assert float(events[0].threshold) == 0.80

    # Call again with the same spend ($85)
    events_repeat = await alert_service.check_and_trigger_alerts(
        db=test_db_session,
        scope=scope,
        period_type=period_type,
        period_start=period_start,
        spent=85.0,
        budget=budget,
        thresholds=thresholds,
    )
    # Deduplication: no new alert events created!
    assert len(events_repeat) == 0

    # Spend increases to $95 (95% > 90%)
    events_90 = await alert_service.check_and_trigger_alerts(
        db=test_db_session,
        scope=scope,
        period_type=period_type,
        period_start=period_start,
        spent=95.0,
        budget=budget,
        thresholds=thresholds,
    )
    # Only 90% threshold should trigger (80% already recorded)
    assert len(events_90) == 1
    assert float(events_90[0].threshold) == 0.90

    # Check total persisted alert records
    stmt = select(AlertEvent).where(AlertEvent.scope == scope)
    all_events = (await test_db_session.execute(stmt)).scalars().all()
    assert len(all_events) == 2


@pytest.mark.asyncio
async def test_webhook_dispatch_invoked():
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value.status_code = 200
        with patch.object(alert_service.settings, "ALERT_WEBHOOK_URL", "https://hooks.example.com/test"):
            payload = {
                "scope": "global",
                "period_type": "daily",
                "threshold_percent": 80.0,
                "spent_amount": 80.0,
                "budget_amount": 100.0,
                "percent_used": 80.0,
                "timestamp": "2025-01-01T00:00:00Z",
            }
            await alert_service._dispatch_webhook(payload)
            mock_post.assert_called_once()

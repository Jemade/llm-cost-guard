from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.logging import logger
from app.models.alert import AlertEvent


class AlertService:
    """
    Evaluates spending thresholds, persists triggered alerts,
    prevents duplicate spamming, and dispatches to console and webhooks.
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    async def check_and_trigger_alerts(
        self,
        db: AsyncSession,
        scope: str,
        period_type: str,
        period_start: datetime,
        spent: float,
        budget: Optional[float],
        thresholds: List[float],
    ) -> List[AlertEvent]:
        """
        Evaluates spent amount against budget thresholds.
        Creates and dispatches alerts for newly crossed thresholds.
        """
        if not budget or budget <= 0:
            return []

        triggered_events: List[AlertEvent] = []
        percent_used = spent / budget

        for threshold in sorted(thresholds):
            if percent_used >= threshold:
                # Check if this threshold was already alerted in this period
                stmt = select(AlertEvent).where(
                    AlertEvent.scope == scope,
                    AlertEvent.period_type == period_type,
                    AlertEvent.period_start == period_start,
                    AlertEvent.threshold == Decimal(str(threshold)),
                )
                result = await db.execute(stmt)
                existing = result.scalar_one_or_none()

                if not existing:
                    # Persist new alert event
                    payload = {
                        "scope": scope,
                        "period_type": period_type,
                        "threshold_percent": round(threshold * 100, 1),
                        "spent_amount": round(spent, 6),
                        "budget_amount": round(budget, 4),
                        "percent_used": round(percent_used * 100, 2),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }

                    alert_event = AlertEvent(
                        scope=scope,
                        period_type=period_type,
                        period_start=period_start,
                        threshold=Decimal(str(threshold)),
                        spent_amount=Decimal(str(spent)),
                        budget_amount=Decimal(str(budget)),
                        channel="console_and_webhook" if self.settings.ALERT_WEBHOOK_URL else "console",
                        status="DELIVERED",
                        payload=payload,
                    )
                    db.add(alert_event)
                    await db.flush()

                    # Dispatch to console
                    self._dispatch_console_alert(payload)

                    # Dispatch to webhook if configured
                    if self.settings.ALERT_WEBHOOK_URL:
                        await self._dispatch_webhook(payload)

                    triggered_events.append(alert_event)

        return triggered_events

    def _dispatch_console_alert(self, payload: dict) -> None:
        """Outputs high-visibility structured alert to console logs."""
        scope = payload["scope"]
        period = payload["period_type"]
        pct = payload["threshold_percent"]
        spent = payload["spent_amount"]
        budget = payload["budget_amount"]

        msg = (
            f"\n"
            f"==========================================================\n"
            f"⚠️  BUDGET ALERT: {pct}% THRESHOLD EXCEEDED\n"
            f"Scope:       {scope}\n"
            f"Period:      {period.upper()}\n"
            f"Spent:       ${spent:.4f} / ${budget:.2f} ({payload['percent_used']}%)\n"
            f"Timestamp:   {payload['timestamp']}\n"
            f"=========================================================="
        )
        logger.warning(msg)

    async def _dispatch_webhook(self, payload: dict) -> None:
        """Sends HTTP POST alert to external webhook (Slack, Discord, or custom)."""
        webhook_url = self.settings.ALERT_WEBHOOK_URL
        if not webhook_url:
            return

        # Prepare payload compatible with Slack/Discord and standard webhooks
        formatted_text = (
            f"⚠️ *LLM Cost Guard Budget Alert*\n"
            f"• *Scope*: `{payload['scope']}`\n"
            f"• *Period*: {payload['period_type'].title()}\n"
            f"• *Threshold*: {payload['threshold_percent']}%\n"
            f"• *Spent*: ${payload['spent_amount']:.4f} / ${payload['budget_amount']:.2f} ({payload['percent_used']}%)\n"
            f"• *Timestamp*: {payload['timestamp']}"
        )
        body = {
            "text": formatted_text,
            "event": "budget_threshold_exceeded",
            "data": payload,
        }

        retries = self.settings.ALERT_WEBHOOK_MAX_RETRIES
        timeout = self.settings.ALERT_WEBHOOK_TIMEOUT_SECONDS

        for attempt in range(1, retries + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(webhook_url, json=body)
                    if response.status_code < 400:
                        logger.info(f"Successfully delivered budget alert webhook (status {response.status_code})")
                        return
                    else:
                        logger.warning(
                            f"Webhook attempt {attempt} returned non-200 status {response.status_code}: {response.text}"
                        )
            except Exception as exc:
                logger.warning(f"Webhook attempt {attempt} failed with error: {exc}")


alert_service = AlertService()

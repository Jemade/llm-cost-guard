from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional
import uuid

from sqlalchemy import (
    DateTime,
    Index,
    JSON,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AlertEvent(Base):
    __tablename__ = "alert_events"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    scope: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    period_type: Mapped[str] = mapped_column(String(32), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    threshold: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    spent_amount: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    budget_amount: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="console")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DELIVERED")
    payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint(
            "scope",
            "period_type",
            "period_start",
            "threshold",
            name="uq_alert_scope_period_threshold",
        ),
        Index("ix_alerts_scope_created", "scope", "created_at"),
    )

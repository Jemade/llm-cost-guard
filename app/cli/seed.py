import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import random
import sys
import uuid

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from sqlalchemy import delete

from app.core.database import Base, async_session_factory, engine
from app.models.budget import BudgetConfig
from app.models.usage import LLMUsageLog
from app.services.cost_calculator import cost_calculator
from app.services.pricing_catalog import pricing_catalog

SAMPLE_MODELS = [
    ("openai", "gpt-4o", [200, 1500], [50, 400]),
    ("openai", "gpt-4o-mini", [100, 3000], [50, 800]),
    ("anthropic", "claude-3-5-sonnet", [300, 2500], [100, 600]),
    ("google", "gemini-1.5-flash", [500, 8000], [100, 1000]),
    ("deepseek", "deepseek-chat", [400, 4000], [100, 700]),
]

SAMPLE_ENDPOINTS = [
    "/v1/chat/completions",
    "/v1/agent/task",
    "/v1/summarize",
    "/v1/embeddings",
]

SAMPLE_USERS = [
    "user_alice",
    "user_bob",
    "team_platform",
    "team_data_science",
    "svc_evaluator",
]


async def seed_data(num_records: int = 150) -> None:
    """
    Seeds realistic sample usage data for local testing and demonstration.
    All seeded records are explicitly marked with metadata {'is_sample_data': True}.
    """
    print("[*] Initializing database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        print("[*] Configuring sample global budget ($10/day, $50/week, $200/month)...")
        # Ensure clean global budget config
        await session.execute(delete(BudgetConfig).where(BudgetConfig.scope == "global"))
        sample_budget = BudgetConfig(
            id=str(uuid.uuid4()),
            scope="global",
            daily_budget=Decimal("10.00"),
            weekly_budget=Decimal("50.00"),
            monthly_budget=Decimal("200.00"),
            alert_thresholds=[0.80, 0.90, 1.00],
            is_active=True,
        )
        session.add(sample_budget)

        print(f"[*] Generating {num_records} sample usage records...")
        now = datetime.now(timezone.utc)

        for i in range(num_records):
            provider, model, in_range, out_range = random.choice(SAMPLE_MODELS)
            pricing = pricing_catalog.get(provider, model)

            in_tokens = random.randint(*in_range)
            out_tokens = random.randint(*out_range)
            total_tokens = in_tokens + out_tokens

            # Stagger timestamps across the last 14 days
            days_ago = random.uniform(0, 14)
            timestamp = now - timedelta(days=days_ago)

            est_in, est_out, est_total = cost_calculator.calculate(
                in_tokens, out_tokens, pricing
            )

            # Occasionally simulate small variance between estimated and actual
            actual_in = max(0, in_tokens + random.randint(-5, 5))
            actual_out = max(0, out_tokens + random.randint(-10, 10))
            _, _, actual_total = cost_calculator.calculate(
                actual_in, actual_out, pricing
            )

            # 94% SUCCESS, 4% BLOCKED, 2% FAILED
            status_roll = random.random()
            if status_roll < 0.94:
                status = "SUCCESS"
            elif status_roll < 0.98:
                status = "BLOCKED"
            else:
                status = "FAILED"

            record = LLMUsageLog(
                id=str(uuid.uuid4()),
                request_id=f"req_sample_{uuid.uuid4().hex[:12]}",
                user_id=random.choice(SAMPLE_USERS),
                endpoint=random.choice(SAMPLE_ENDPOINTS),
                provider=provider,
                model=model,
                input_tokens=in_tokens,
                output_tokens=out_tokens,
                total_tokens=total_tokens,
                estimated_cost=Decimal(str(est_total)),
                actual_cost=Decimal(str(actual_total)) if status == "SUCCESS" else None,
                latency_ms=round(random.uniform(120.0, 1850.0), 1),
                status=status,
                timestamp=timestamp,
                metadata_json={
                    "is_sample_data": True,
                    "seed_batch": "portfolio_demo",
                },
            )
            session.add(record)

        await session.commit()
        print(f"[+] Successfully inserted {num_records} sample usage records.")
        print("[+] Sample data is ready! Open http://localhost:8000/dashboard to view.")


if __name__ == "__main__":
    asyncio.run(seed_data())

"""
LLM Cost Guard - Reproducible Cost-Saving & Budget Blocking Demonstration

Demonstrates:
1. Setting up a controlled daily budget of $10.00.
2. Simulating existing spend of $9.70 (remaining daily budget: $0.30).
3. Attempting an expensive model call (Claude 3 Opus, estimated cost ~$0.42) -> BLOCKED.
4. Attempting an optimized, cost-effective model call (GPT-4o Mini, estimated cost ~$0.004) -> ALLOWED.
5. Recording actual usage and showing updated remaining budget.

Can be run directly via:
    python examples/budget_control_demo.py
"""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import sys
import uuid

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete

from app.core.database import Base, async_session_factory, engine
from app.models.alert import AlertEvent
from app.models.budget import BudgetReservation
from app.models.usage import LLMUsageLog
from app.services.budget_service import budget_service
from app.services.cost_calculator import cost_calculator
from app.services.pricing_catalog import pricing_catalog
from app.services.token_estimator import token_estimator


async def run_in_process_demo():
    print("=" * 70)
    print("       LLM COST GUARD - BUDGET CONTROL & BLOCKING DEMO")
    print("=" * 70)

    # 1. Initialize schema
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    demo_scope = "user:demo_client"
    demo_user = "demo_client"

    async with async_session_factory() as db:
        # Reset previous demo state for idempotence
        await db.execute(delete(LLMUsageLog).where(LLMUsageLog.user_id == demo_user))
        await db.execute(delete(BudgetReservation).where(BudgetReservation.scope == demo_scope))
        await db.execute(delete(AlertEvent).where(AlertEvent.scope == demo_scope))

        # 2. Configure a strict daily budget: $10.00
        print(f"\n[Step 1] Configuring daily budget for '{demo_scope}': $10.00")
        config = await budget_service.get_or_create_budget(db, scope=demo_scope)
        config.daily_budget = Decimal("10.00")
        config.weekly_budget = Decimal("50.00")
        config.monthly_budget = Decimal("200.00")
        await db.flush()

        # 3. Simulate existing spend of $9.70 today (remaining = $0.30)
        print("[Step 2] Simulating prior usage of $9.70 today...")
        existing_log = LLMUsageLog(
            id=str(uuid.uuid4()),
            request_id=f"req_prior_{uuid.uuid4().hex[:8]}",
            user_id=demo_user,
            endpoint="/v1/chat/completions",
            provider="openai",
            model="gpt-4o",
            input_tokens=25000,
            output_tokens=9075,
            total_tokens=34075,
            estimated_cost=Decimal("0.970000"),
            actual_cost=Decimal("9.700000"),
            latency_ms=450.0,
            status="SUCCESS",
            timestamp=datetime.now(timezone.utc),
        )
        db.add(existing_log)
        await db.commit()

    async with async_session_factory() as db:
        # Check current status
        daily_spent = await budget_service.calculate_period_spend(
            db, demo_scope, budget_service.get_period_starts()["daily"]
        )
        remaining = round(10.00 - daily_spent, 4)
        print("         Current Daily Budget: $10.00")
        print(f"         Current Spent Today:  ${daily_spent:.4f}")
        print(f"         Remaining Budget:     ${remaining:.4f}")

        # 4. Attempt an expensive request: Claude 3 Opus
        # 10,000 prompt tokens + 3,600 output tokens on claude-3-opus ($15/1M in, $75/1M out)
        # Cost = (10,000 / 1M * $15.00) + (3,600 / 1M * $75.00) = $0.15 + $0.27 = $0.42
        expensive_model = "claude-3-opus"
        expensive_provider = "anthropic"
        expensive_pricing = pricing_catalog.get(expensive_provider, expensive_model)

        # A prompt yielding ~10,000 tokens
        sample_prompt = "Perform deep architectural analysis and formal verification: " + ("system architecture component state transition " * 1850)
        exp_in_tokens, _, _, _ = token_estimator.estimate_input_tokens(
            pricing=expensive_pricing, prompt=sample_prompt
        )
        exp_expected_out = 3600
        _, _, exp_cost = cost_calculator.calculate(
            exp_in_tokens, exp_expected_out, expensive_pricing
        )

        print(f"\n[Step 3] Pre-flight Check: Expensive Request ({expensive_provider}/{expensive_model})")
        print(f"         Prompt Tokens:     {exp_in_tokens:,}")
        print(f"         Expected Output:   {exp_expected_out:,}")
        print(f"         Estimated Cost:    ${exp_cost:.4f}")
        print(f"         Remaining Budget:  ${remaining:.4f}")

        decision, reason, periods, _ = await budget_service.check_budget(
            db=db,
            estimated_cost=exp_cost,
            scope=demo_scope,
            reserve=False,
        )

        print(f"         --> DECISION: {decision}")
        print(f"         --> REASON:   {reason}")

        if decision == "BLOCK":
            print("         🛡️  [PROTECTION ACTIVE] Request blocked before calling provider!")
            # Log blocked request
            blocked_log = LLMUsageLog(
                id=str(uuid.uuid4()),
                request_id=f"req_blocked_{uuid.uuid4().hex[:8]}",
                user_id=demo_user,
                endpoint="/v1/chat/completions",
                provider=expensive_provider,
                model=expensive_model,
                input_tokens=exp_in_tokens,
                output_tokens=0,
                total_tokens=exp_in_tokens,
                estimated_cost=Decimal(str(exp_cost)),
                actual_cost=None,
                status="BLOCKED",
                timestamp=datetime.now(timezone.utc),
            )
            db.add(blocked_log)
            await db.commit()

        # 5. Attempt an optimized request: GPT-4o-mini
        # Same prompt, same expected output
        cheap_model = "gpt-4o-mini"
        cheap_provider = "openai"
        cheap_pricing = pricing_catalog.get(cheap_provider, cheap_model)

        cheap_in_tokens, _, _, _ = token_estimator.estimate_input_tokens(
            pricing=cheap_pricing, prompt=sample_prompt
        )
        cheap_expected_out = 3600
        _, _, cheap_cost = cost_calculator.calculate(
            cheap_in_tokens, cheap_expected_out, cheap_pricing
        )

        print(f"\n[Step 4] Fallback Attempt: Cost-Optimized Request ({cheap_provider}/{cheap_model})")
        print(f"         Prompt Tokens:     {cheap_in_tokens:,}")
        print(f"         Expected Output:   {cheap_expected_out:,}")
        print(f"         Estimated Cost:    ${cheap_cost:.6f}")
        print(f"         Remaining Budget:  ${remaining:.4f}")

        decision2, reason2, periods2, reservation_id = await budget_service.check_budget(
            db=db,
            estimated_cost=cheap_cost,
            scope=demo_scope,
            reserve=True,
        )

        print(f"         --> DECISION: {decision2}")
        print(f"         --> REASON:   {reason2}")

        if decision2 == "ALLOW":
            print("         ✅ [APPROVED] Request fits within remaining budget.")
            print(f"         Reservation ID held: {reservation_id}")

            # Simulate LLM call completion and usage record
            usage_log = LLMUsageLog(
                id=str(uuid.uuid4()),
                request_id=f"req_success_{uuid.uuid4().hex[:8]}",
                user_id=demo_user,
                endpoint="/v1/chat/completions",
                provider=cheap_provider,
                model=cheap_model,
                input_tokens=cheap_in_tokens,
                output_tokens=cheap_expected_out,
                total_tokens=cheap_in_tokens + cheap_expected_out,
                estimated_cost=Decimal(str(cheap_cost)),
                actual_cost=Decimal(str(cheap_cost)),
                latency_ms=310.0,
                status="SUCCESS",
                timestamp=datetime.now(timezone.utc),
            )
            db.add(usage_log)
            if reservation_id:
                await budget_service.commit_reservation(db, reservation_id)
            await db.commit()

            new_spent = await budget_service.calculate_period_spend(
                db, demo_scope, budget_service.get_period_starts()["daily"]
            )
            print("\n[Step 5] Final Status:")
            print(f"         New Daily Spent:     ${new_spent:.4f} / $10.00")
            print(f"         New Remaining:       ${(10.00 - new_spent):.4f}")
            print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_in_process_demo())

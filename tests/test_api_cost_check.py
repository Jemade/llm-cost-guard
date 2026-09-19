import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_cost_check_endpoint_allow(client: AsyncClient):
    payload = {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "prompt": "Say hello!",
        "expected_output_tokens": 50,
        "user_id": "test_user_allow",
    }
    response = await client.post("/v1/cost/check", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == "ALLOW"
    assert data["reason"] == "WITHIN_BUDGET"
    assert data["estimated_cost"] > 0
    assert "daily" in data


@pytest.mark.asyncio
async def test_cost_check_endpoint_block_zero_budget(client: AsyncClient):
    # Configure user with $0 budget
    await client.post(
        "/v1/budgets",
        json={"scope": "user:blocked_user", "daily_budget": 0.0},
    )

    payload = {
        "provider": "openai",
        "model": "gpt-4o",
        "prompt": "Complex reasoning task...",
        "expected_output_tokens": 100,
        "user_id": "blocked_user",
    }
    response = await client.post("/v1/cost/check", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == "BLOCK"
    assert data["reason"] == "ZERO_BUDGET_CONFIGURED"


@pytest.mark.asyncio
async def test_cost_check_with_reservation(client: AsyncClient):
    payload = {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "prompt": "Generate a test response",
        "expected_output_tokens": 20,
        "user_id": "reserve_user",
        "reserve": True,
    }
    response = await client.post("/v1/cost/check", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == "ALLOW"
    assert data["reservation_id"] is not None

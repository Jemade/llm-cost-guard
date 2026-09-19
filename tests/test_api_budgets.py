import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_and_set_budgets(client: AsyncClient):
    # 1. Set a custom budget
    set_payload = {
        "scope": "user:charlie",
        "daily_budget": 15.00,
        "weekly_budget": 75.00,
        "monthly_budget": 300.00,
        "alert_thresholds": [0.75, 0.90, 1.00],
    }
    set_resp = await client.post("/v1/budgets", json=set_payload)
    assert set_resp.status_code == 200
    data = set_resp.json()
    assert data["scope"] == "user:charlie"
    assert data["daily_budget"] == 15.00
    assert data["weekly_budget"] == 75.00
    assert data["monthly_budget"] == 300.00
    assert data["alert_thresholds"] == [0.75, 0.90, 1.00]

    # 2. Get budgets
    get_resp = await client.get("/v1/budgets?scope=user:charlie")
    assert get_resp.status_code == 200
    budgets = get_resp.json()
    assert len(budgets) == 1
    assert budgets[0]["scope"] == "user:charlie"
    assert budgets[0]["daily"]["budget"] == 15.00

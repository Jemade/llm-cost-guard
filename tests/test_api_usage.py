import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_record_and_list_usage(client: AsyncClient):
    # 1. Record usage
    record_payload = {
        "request_id": "req_test_12345",
        "user_id": "alice",
        "endpoint": "/v1/chat/completions",
        "provider": "openai",
        "model": "gpt-4o",
        "input_tokens": 500,
        "output_tokens": 150,
        "estimated_cost": 0.00275,
        "actual_cost": 0.00275,
        "latency_ms": 350.5,
        "status": "SUCCESS",
    }
    create_resp = await client.post("/v1/usage", json=record_payload)
    assert create_resp.status_code == 201
    created_data = create_resp.json()
    assert created_data["request_id"] == "req_test_12345"
    assert created_data["total_tokens"] == 650
    assert created_data["estimated_cost"] == 0.00275
    assert created_data["actual_cost"] == 0.00275

    # 2. List usage without filters
    list_resp = await client.get("/v1/usage")
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert len(items) >= 1

    # 3. Filter by user_id
    alice_resp = await client.get("/v1/usage?user_id=alice")
    assert alice_resp.status_code == 200
    assert all(item["user_id"] == "alice" for item in alice_resp.json())

    # 4. Filter by non-existent user
    bob_resp = await client.get("/v1/usage?user_id=non_existent_bob")
    assert bob_resp.status_code == 200
    assert len(bob_resp.json()) == 0

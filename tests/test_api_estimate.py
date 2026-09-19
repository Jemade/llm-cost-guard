import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_estimate_endpoint_with_prompt(client: AsyncClient):
    payload = {
        "provider": "openai",
        "model": "gpt-4o",
        "prompt": "Summarize the key architectural benefits of microservices.",
        "expected_output_tokens": 150,
    }
    response = await client.post("/v1/estimate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "openai"
    assert data["model"] == "gpt-4o"
    assert data["estimated_input_tokens"] > 0
    assert data["estimated_output_tokens"] == 150
    assert data["estimated_total_tokens"] == data["estimated_input_tokens"] + 150
    assert data["estimated_total_cost"] > 0
    assert data["confidence"] == "exact"


@pytest.mark.asyncio
async def test_estimate_endpoint_with_messages(client: AsyncClient):
    payload = {
        "provider": "anthropic",
        "model": "claude-3-5-sonnet",
        "messages": [
            {"role": "system", "content": "You are a code reviewer."},
            {"role": "user", "content": "Check this function for memory leaks."},
        ],
        "expected_output_tokens": 200,
    }
    response = await client.post("/v1/estimate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "anthropic"
    assert data["confidence"] == "approximation"


@pytest.mark.asyncio
async def test_estimate_unknown_model_returns_404(client: AsyncClient):
    payload = {
        "provider": "unknown_provider",
        "model": "unknown_model",
        "prompt": "Test",
    }
    response = await client.post("/v1/estimate", json=payload)
    assert response.status_code == 404
    assert "No pricing configured" in response.json()["detail"]


@pytest.mark.asyncio
async def test_estimate_missing_input_returns_422(client: AsyncClient):
    payload = {
        "provider": "openai",
        "model": "gpt-4o",
    }
    response = await client.post("/v1/estimate", json=payload)
    assert response.status_code == 422

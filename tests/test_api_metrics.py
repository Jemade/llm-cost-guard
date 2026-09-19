import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["database"] == "ok"


@pytest.mark.asyncio
async def test_metrics_endpoint(client: AsyncClient):
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert "costguard_total_spend_usd" in data
    assert "costguard_models_configured_count" in data
    assert data["costguard_models_configured_count"] >= 10


@pytest.mark.asyncio
async def test_analytics_summary_endpoint(client: AsyncClient):
    resp = await client.get("/v1/analytics/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_spend" in data
    assert "tokens" in data
    assert "requests" in data


@pytest.mark.asyncio
async def test_dashboard_html_renders(client: AsyncClient):
    resp = await client.get("/dashboard")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "LLM Cost Guard" in resp.text
    assert "Spend by Model" in resp.text


@pytest.mark.asyncio
async def test_alerts_endpoint(client: AsyncClient):
    resp = await client.get("/v1/alerts")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

import pytest

from app.core.exceptions import ModelPricingNotFoundError
from app.services.pricing_catalog import PricingCatalog, pricing_catalog


def test_pricing_catalog_loads_models():
    models = pricing_catalog.list_models()
    assert len(models) >= 10
    gpt4o = pricing_catalog.get("openai", "gpt-4o")
    assert gpt4o.provider == "openai"
    assert gpt4o.model == "gpt-4o"
    assert gpt4o.input_cost_per_1m_tokens == 2.50
    assert gpt4o.output_cost_per_1m_tokens == 10.00
    assert gpt4o.currency == "USD"
    assert gpt4o.effective_date != ""
    assert gpt4o.last_verified != ""


def test_pricing_catalog_case_insensitive():
    pricing1 = pricing_catalog.get("OpenAI", "GPT-4O")
    pricing2 = pricing_catalog.get("openai", "gpt-4o")
    assert pricing1 == pricing2


def test_pricing_catalog_missing_model_raises():
    with pytest.raises(ModelPricingNotFoundError) as exc_info:
        pricing_catalog.get("openai", "non-existent-model-xyz")
    assert "non-existent-model-xyz" in str(exc_info.value)


def test_pricing_catalog_dynamic_reload(tmp_path):
    custom_yaml = tmp_path / "pricing.yaml"
    custom_yaml.write_text(
        """
version: "2.0.0"
currency: "USD"
models:
  - provider: "custom_provider"
    model: "custom-v1"
    input_cost_per_1m_tokens: 1.00
    output_cost_per_1m_tokens: 2.00
    effective_date: "2025-01-01"
    last_verified: "2025-01-01"
"""
    )
    custom_catalog = PricingCatalog(config_path=str(custom_yaml))
    assert custom_catalog.version == "2.0.0"
    m = custom_catalog.get("custom_provider", "custom-v1")
    assert m.input_cost_per_1m_tokens == 1.00

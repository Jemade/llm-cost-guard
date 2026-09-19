from app.services.cost_calculator import cost_calculator
from app.services.pricing_catalog import pricing_catalog


def test_cost_calculation_one_million_tokens():
    pricing = pricing_catalog.get("openai", "gpt-4o")
    # gpt-4o: $2.50 / 1M in, $10.00 / 1M out
    in_cost, out_cost, total = cost_calculator.calculate(
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        pricing=pricing,
    )
    assert in_cost == 2.50
    assert out_cost == 10.00
    assert total == 12.50


def test_cost_calculation_zero_tokens():
    pricing = pricing_catalog.get("openai", "gpt-4o-mini")
    in_cost, out_cost, total = cost_calculator.calculate(
        input_tokens=0,
        output_tokens=0,
        pricing=pricing,
    )
    assert in_cost == 0.0
    assert out_cost == 0.0
    assert total == 0.0


def test_cost_calculation_fractional_precision():
    pricing = pricing_catalog.get("openai", "gpt-4o-mini")
    # gpt-4o-mini: $0.15 / 1M in, $0.60 / 1M out
    # 1,000 in = 0.00015, 1,000 out = 0.0006, total = 0.00075
    in_cost, out_cost, total = cost_calculator.calculate(
        input_tokens=1000,
        output_tokens=1000,
        pricing=pricing,
    )
    assert in_cost == 0.00015
    assert out_cost == 0.0006
    assert total == 0.00075


def test_negative_tokens_treated_as_zero():
    pricing = pricing_catalog.get("google", "gemini-1.5-flash")
    in_cost, out_cost, total = cost_calculator.calculate(
        input_tokens=-50,
        output_tokens=-100,
        pricing=pricing,
    )
    assert in_cost == 0.0
    assert out_cost == 0.0
    assert total == 0.0

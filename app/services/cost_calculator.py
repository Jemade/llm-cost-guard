from decimal import ROUND_HALF_UP, Decimal
from typing import Tuple

from app.schemas.pricing import ModelPricingSchema


class CostCalculator:
    """
    Computes precise monetary costs based on token quantities and model pricing rates.
    Uses Decimal arithmetic to prevent floating point inaccuracies.
    """

    ONE_MILLION = Decimal("1000000")

    @classmethod
    def calculate(
        cls,
        input_tokens: int,
        output_tokens: int,
        pricing: ModelPricingSchema,
    ) -> Tuple[float, float, float]:
        """
        Calculates (input_cost, output_cost, total_cost) in USD.
        Rounded to 6 decimal places.
        """
        in_tokens_dec = Decimal(str(max(0, input_tokens)))
        out_tokens_dec = Decimal(str(max(0, output_tokens)))

        in_rate = Decimal(str(pricing.input_cost_per_1m_tokens))
        out_rate = Decimal(str(pricing.output_cost_per_1m_tokens))

        input_cost = (in_tokens_dec / cls.ONE_MILLION) * in_rate
        output_cost = (out_tokens_dec / cls.ONE_MILLION) * out_rate
        total_cost = input_cost + output_cost

        # Round to 6 decimal places (micro-dollars: $0.000001)
        input_cost_rounded = float(input_cost.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))
        output_cost_rounded = float(output_cost.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))
        total_cost_rounded = float(total_cost.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))

        return input_cost_rounded, output_cost_rounded, total_cost_rounded


cost_calculator = CostCalculator()

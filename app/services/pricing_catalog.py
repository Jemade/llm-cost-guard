from pathlib import Path
from typing import Dict, List, Optional

import yaml

from app.config import get_settings
from app.core.exceptions import ModelPricingNotFoundError
from app.core.logging import logger
from app.schemas.pricing import ModelPricingSchema, PricingCatalogSchema


class PricingCatalog:
    """
    Manages provider and model pricing loaded from YAML configuration.
    Allows dynamic updates without modifying application code.
    """

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = Path(config_path or get_settings().PRICING_FILE_PATH)
        self._pricing_by_key: Dict[str, ModelPricingSchema] = {}
        self.version: str = "unknown"
        self.currency: str = "USD"
        self.load()

    def _make_key(self, provider: str, model: str) -> str:
        return f"{provider.strip().lower()}:{model.strip().lower()}"

    def load(self) -> None:
        """Loads and parses the pricing YAML configuration."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Pricing configuration file not found: {self.config_path}")

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                raw_data = yaml.safe_load(f)

            catalog = PricingCatalogSchema.model_validate(raw_data)
            self.version = catalog.version
            self.currency = catalog.currency
            self._pricing_by_key.clear()

            for item in catalog.models:
                key = self._make_key(item.provider, item.model)
                self._pricing_by_key[key] = item

            logger.info(
                f"Loaded {len(self._pricing_by_key)} model pricing configurations (v{self.version}) from {self.config_path}"
            )
        except Exception as e:
            logger.error(f"Failed to load pricing configuration from {self.config_path}: {e}")
            raise

    def reload(self) -> None:
        """Hot-reloads the pricing configuration from disk."""
        self.load()

    def get(self, provider: str, model: str) -> ModelPricingSchema:
        """
        Retrieves pricing for a specific provider and model.
        Raises ModelPricingNotFoundError if not found.
        """
        key = self._make_key(provider, model)
        pricing = self._pricing_by_key.get(key)
        if not pricing:
            raise ModelPricingNotFoundError(provider, model)
        return pricing

    def list_models(self) -> List[ModelPricingSchema]:
        """Returns all registered model pricing configurations."""
        return list(self._pricing_by_key.values())


# Singleton instance initialized with default configuration path
pricing_catalog = PricingCatalog()

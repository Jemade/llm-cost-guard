"""Custom domain exceptions for LLM Cost Guard."""


class CostGuardError(Exception):
    """Base exception for all domain errors."""
    pass


class ModelPricingNotFoundError(CostGuardError):
    """Raised when a requested model is not found in the pricing catalog."""
    def __init__(self, provider: str, model: str):
        super().__init__(f"No pricing configured for provider '{provider}' and model '{model}'.")
        self.provider = provider
        self.model = model


class BudgetExceededError(CostGuardError):
    """Raised when a request exceeds configured budget limits."""
    def __init__(self, reason: str, remaining: float, requested: float):
        super().__init__(f"Budget exceeded: {reason}. Remaining: ${remaining:.6f}, Requested: ${requested:.6f}")
        self.reason = reason
        self.remaining = remaining
        self.requested = requested


class InvalidTokenizerError(CostGuardError):
    """Raised when tokenizer configuration or approximation fails."""
    pass


class ConcurrencyLockError(CostGuardError):
    """Raised when failing to acquire a lock or reservation for budget check."""
    pass

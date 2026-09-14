"""Explicit AI module errors. No 503 mapping here: that belongs to the API
boundary of each consumer change (API.md)."""

from pydantic import ValidationError


class AIProviderNotConfiguredError(Exception):
    """Raised when a capability runs with no configured provider (adapter is None)."""

    def __init__(self, prompt_id: str) -> None:
        super().__init__(f"AI provider not configured for capability '{prompt_id}'")
        self.prompt_id = prompt_id


class AIPromptNotFoundError(Exception):
    """Raised when a prompt id is not present in the versioned registry."""

    def __init__(self, prompt_id: str) -> None:
        super().__init__(f"Prompt '{prompt_id}' is not registered")
        self.prompt_id = prompt_id


class AIOutputValidationError(Exception):
    """Raised when a model output does not satisfy its structured contract."""

    def __init__(self, contract: str, cause: ValidationError) -> None:
        super().__init__(f"Model output does not satisfy contract '{contract}'")
        self.contract = contract
        self.cause = cause


class AIProviderResponseError(Exception):
    """Raised when a provider response cannot be parsed at all (e.g. non-JSON)."""

    def __init__(self, model: str) -> None:
        super().__init__(f"Provider '{model}' returned an unparseable response")
        self.model = model

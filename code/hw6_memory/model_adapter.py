"""HW6 adapter facade that normally delegates to the reusable HW1 Ollama client."""

from functools import lru_cache
from typing import Any

from src.model_client import ModelClient

from .config import get_settings
from .utils import estimate_tokens


class DeterministicModelClient:
    """Small local test double used only when HW6_USE_DETERMINISTIC_MODEL=true.

    It keeps smoke tests objective and offline. Normal application runs use the
    HW1 ``ModelClient`` and its local Ollama connection instead.
    """

    def __init__(self) -> None:
        self.cumulative_input_tokens = 0
        self.cumulative_output_tokens = 0
        self.turn_count = 0

    def complete(self, messages: list[dict[str, str]], tools: list[Any] | None = None) -> dict[str, Any]:
        user_message = next((item["content"] for item in reversed(messages) if item["role"] == "user"), "")
        if "Current user message:\n" in user_message:
            user_message = user_message.rsplit("Current user message:\n", 1)[1]
        content = f"Recorded your rental-housing request: {user_message}"
        input_tokens = sum(estimate_tokens(item["content"]) for item in messages)
        output_tokens = estimate_tokens(content)
        self.cumulative_input_tokens += input_tokens
        self.cumulative_output_tokens += output_tokens
        self.turn_count += 1
        return {
            "content": content,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cumulative_input_tokens": self.cumulative_input_tokens,
            "cumulative_output_tokens": self.cumulative_output_tokens,
            "turn_count": self.turn_count,
        }


@lru_cache
def get_model_client() -> ModelClient | DeterministicModelClient:
    settings = get_settings()
    if settings.use_deterministic_model:
        return DeterministicModelClient()
    return ModelClient(model=settings.model_name, base_url=settings.ollama_base_url)

from __future__ import annotations

from typing import Iterator

from app.config import ModelProfile
from app.models.contract import ModelAdapter, ModelInput, ModelOutput


class DisabledModelAdapter(ModelAdapter):
    """Policy-safe adapter used until a real local model backend is enabled."""

    def __init__(self, profile_name: str, profile: ModelProfile, model_path: str) -> None:
        self._profile_name = profile_name
        self._profile = profile
        self._model_path = model_path

    def complete(self, input: ModelInput) -> ModelOutput:
        context_count = len(input.context)
        return ModelOutput(
            response_text=(
                "Runtime pipeline executed, but model inference is disabled. "
                f"Profile '{self._profile_name}' uses backend '{self._profile.backend}' "
                "with wired=false. Enable a real model adapter only after policy approval. "
                f"Context items prepared: {context_count}."
            ),
            finish_reason="model_disabled",
            token_usage={"input_context_items": context_count, "generated_tokens": 0},
            metadata={
                "backend": self._profile.backend,
                "profile": self._profile_name,
                "model_path": self._model_path,
                "wired": False,
            },
        )

    def stream(self, input: ModelInput) -> Iterator[str]:
        yield self.complete(input).response_text

    def health(self) -> dict:
        return {
            "component": "model",
            "healthy": True,
            "wired": False,
            "backend": self._profile.backend,
            "profile": self._profile_name,
            "detail": "Adapter boundary is available; execution disabled by config.",
        }

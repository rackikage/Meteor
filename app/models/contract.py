from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator


@dataclass
class ModelInput:
    prompt: str
    context: list[dict] = field(default_factory=list)
    max_tokens: int = 512
    temperature: float = 0.7
    metadata: dict = field(default_factory=dict)


@dataclass
class ModelOutput:
    response_text: str
    finish_reason: str
    token_usage: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


class ModelAdapter:
    """Abstract interface. All model adapters must implement this contract."""

    def complete(self, input: ModelInput) -> ModelOutput:
        raise NotImplementedError

    def stream(self, input: ModelInput) -> Iterator[str]:
        raise NotImplementedError

    def health(self) -> dict:
        raise NotImplementedError

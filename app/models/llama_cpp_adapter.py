"""Llama.cpp adapter — local GGUF model inference with streaming support.

Meteor Doctrine #3: Adapters isolate change. This adapter wraps llama-cpp-python
to provide the ModelAdapter contract. Swapping to Ollama, vLLM, or a remote API
requires changes only in this file.

Meteor Doctrine #6: Retrieval is separate from inference. This adapter receives
a pre-built context (from the context builder) — it never performs retrieval.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterator, Optional

from app.config import ModelProfile
from app.models.contract import ModelAdapter, ModelInput, ModelOutput

logger = logging.getLogger(__name__)


class LlamaCppAdapter(ModelAdapter):
    """Local GGUF model inference via llama-cpp-python.

    Supports completion, streaming, and token counting. Respects model profile
    settings (context_window, temperature, max_tokens).
    """

    def __init__(self, profile: ModelProfile, repo_root: Path) -> None:
        self.profile = profile
        self.repo_root = repo_root
        self._model = None
        self._load_model()

    def _load_model(self) -> None:
        """Lazy-load the model on first use."""
        try:
            from llama_cpp import Llama
        except ImportError:
            raise ImportError(
                "llama-cpp-python is required for local inference. "
                "Install with: pip install llama-cpp-python"
            )

        model_path = Path(self.profile.model_path)
        if not model_path.is_absolute():
            model_path = (self.repo_root / model_path).resolve()

        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        logger.info(
            "Loading model: %s (context=%d, n_gpu_layers=-1)",
            model_path.name,
            self.profile.context_window,
        )

        self._model = Llama(
            model_path=str(model_path),
            n_ctx=self.profile.context_window,
            n_gpu_layers=-1,
            verbose=False,
        )

        logger.info("Model loaded successfully")

    def complete(self, input: ModelInput) -> ModelOutput:
        """Run a single completion and return the full response."""
        if self._model is None:
            self._load_model()

        prompt = self._build_prompt(input)

        logger.debug(
            "Completion request: prompt_len=%d, max_tokens=%d, temp=%.2f",
            len(prompt),
            input.max_tokens,
            input.temperature,
        )

        try:
            response = self._model(
                prompt,
                max_tokens=input.max_tokens,
                temperature=input.temperature,
                stop=["</s>"],
                echo=False,
            )

            choice = response["choices"][0]
            finish_reason = choice.get("finish_reason", "unknown")
            text = choice.get("text", "").strip()

            usage = response.get("usage", {})
            token_usage = {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            }

            logger.info(
                "Completion complete: tokens=%d+%d=%d, finish=%s",
                token_usage["prompt_tokens"],
                token_usage["completion_tokens"],
                token_usage["total_tokens"],
                finish_reason,
            )

            return ModelOutput(
                response_text=text,
                finish_reason=finish_reason,
                token_usage=token_usage,
                metadata={"model": self.profile.backend, "profile": self.profile.model_path},
            )

        except Exception as e:
            logger.error("Completion failed: %s", e)
            return ModelOutput(
                response_text="",
                finish_reason="error",
                token_usage={},
                metadata={"error": str(e), "model": self.profile.backend},
            )

    def stream(self, input: ModelInput) -> Iterator[str]:
        """Stream tokens as they are generated."""
        if self._model is None:
            self._load_model()

        prompt = self._build_prompt(input)

        logger.debug(
            "Streaming request: prompt_len=%d, max_tokens=%d, temp=%.2f",
            len(prompt),
            input.max_tokens,
            input.temperature,
        )

        try:
            stream = self._model(
                prompt,
                max_tokens=input.max_tokens,
                temperature=input.temperature,
                stop=["</s>"],
                echo=False,
                stream=True,
            )

            for chunk in stream:
                choice = chunk.get("choices", [{}])[0]
                delta = choice.get("text", "")
                if delta:
                    yield delta

        except Exception as e:
            logger.error("Streaming failed: %s", e)
            yield f"[ERROR: {e}]"

    def health(self) -> dict:
        """Return health status of the model adapter."""
        model_loaded = self._model is not None
        model_path = Path(self.profile.model_path)
        if not model_path.is_absolute():
            model_path = (self.repo_root / model_path).resolve()

        return {
            "healthy": model_loaded and model_path.exists(),
            "backend": self.profile.backend,
            "model_path": str(model_path),
            "model_exists": model_path.exists(),
            "model_loaded": model_loaded,
            "context_window": self.profile.context_window,
            "temperature": self.profile.temperature,
            "max_tokens": self.profile.max_tokens,
        }

    def _build_prompt(self, input: ModelInput) -> str:
        """Build the final prompt from input and context.

        If context is provided, format it as a chat-style prompt.
        Otherwise, use the raw prompt.
        """
        if not input.context:
            return input.prompt

        context_lines = []
        for msg in input.context:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            context_lines.append(f"{role}: {content}")

        context_lines.append(f"assistant: {input.prompt}")
        return "\n".join(context_lines)


def build_llama_cpp_adapter(profile: ModelProfile, repo_root: Path) -> LlamaCppAdapter:
    """Factory function to build a LlamaCppAdapter."""
    return LlamaCppAdapter(profile, repo_root)

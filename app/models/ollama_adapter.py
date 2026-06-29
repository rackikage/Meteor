"""Ollama adapter — local inference via Ollama's HTTP API.

Calls Ollama's REST API at http://localhost:11434 for completions
and streaming. No local model loading required — the Ollama daemon
handles everything.
"""

from __future__ import annotations

import json
import logging
from typing import Iterator

import requests

from app.config import ModelProfile
from app.models.contract import ModelAdapter, ModelInput, ModelOutput

logger = logging.getLogger(__name__)


class OllamaAdapter(ModelAdapter):
    """Calls Ollama's local REST API for completions."""

    def __init__(self, profile: ModelProfile, base_url: str = "http://localhost:11434") -> None:
        self._model = profile.model_path  # model name, e.g., "llama3.2"
        self._base = base_url
        self._temperature = profile.temperature
        self._max_tokens = profile.max_tokens

    def complete(self, input: ModelInput) -> ModelOutput:
        """Send a completion request to Ollama."""
        payload = {
            "model": self._model,
            "prompt": input.prompt,
            "stream": False,
            "options": {
                "temperature": input.temperature or self._temperature,
                "num_predict": input.max_tokens or self._max_tokens,
            },
        }
        try:
            resp = requests.post(
                f"{self._base}/api/generate",
                json=payload,
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            return ModelOutput(
                response_text=data.get("response", ""),
                finish_reason=data.get("done_reason", "stop"),
                token_usage={
                    "prompt_tokens": data.get("prompt_eval_count", 0),
                    "completion_tokens": data.get("eval_count", 0),
                    "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
                },
                metadata={"model": self._model},
            )
        except requests.ConnectionError:
            return ModelOutput(
                response_text="[Ollama not running — start it with: ollama serve]",
                finish_reason="error",
                token_usage={"total_tokens": 0},
                metadata={"error": "connection_refused"},
            )
        except Exception as exc:
            logger.warning("Ollama completion failed: %s", exc)
            return ModelOutput(
                response_text=f"[Meteor]: {exc}",
                finish_reason="error",
                token_usage={"total_tokens": 0},
                metadata={"error": str(exc)},
            )

    def stream(self, input: ModelInput) -> Iterator[str]:
        """Stream tokens from Ollama."""
        payload = {
            "model": self._model,
            "prompt": input.prompt,
            "stream": True,
            "options": {
                "temperature": input.temperature or self._temperature,
                "num_predict": input.max_tokens or self._max_tokens,
            },
        }
        try:
            resp = requests.post(
                f"{self._base}/api/generate",
                json=payload,
                timeout=120,
                stream=True,
            )
            resp.raise_for_status()
            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    token = chunk.get("response", "")
                    if token:
                        yield token
                    if chunk.get("done", False):
                        break
                except json.JSONDecodeError:
                    continue
        except requests.ConnectionError:
            yield "[Ollama not running — start it with: ollama serve]"
        except Exception as exc:
            logger.warning("Ollama stream failed: %s", exc)
            yield f"[Meteor]: {exc}"

    def health(self) -> dict:
        try:
            resp = requests.get(f"{self._base}/api/tags", timeout=5)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                return {"healthy": True, "backend": "ollama", "models": [m["name"] for m in models]}
            return {"healthy": False, "backend": "ollama", "error": f"status {resp.status_code}"}
        except requests.ConnectionError:
            return {"healthy": False, "backend": "ollama", "error": "connection refused"}
        except Exception as exc:
            return {"healthy": False, "backend": "ollama", "error": str(exc)}


def build_ollama_adapter(profile: ModelProfile) -> OllamaAdapter:
    return OllamaAdapter(profile)

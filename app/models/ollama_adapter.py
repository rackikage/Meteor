"""Ollama adapter — local inference via Ollama's HTTP chat API.

Uses /api/chat with num_ctx, task-aware temperature, and streaming.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Iterator

import requests

from app.config import ModelProfile
from app.models.contract import ModelAdapter, ModelInput, ModelOutput
from app.models.task_temperature import resolve_temperature

logger = logging.getLogger(__name__)


class OllamaAdapter(ModelAdapter):
    """Calls Ollama's local REST API for chat completions."""

    def __init__(self, profile: ModelProfile) -> None:
        self._profile = profile
        self._model = profile.model_path
        self._base = profile.base_url.rstrip("/")
        self._context_window = profile.context_window
        self._max_tokens = profile.max_tokens

    def complete(self, input: ModelInput) -> ModelOutput:
        payload = self._build_payload(input, stream=False)
        try:
            resp = requests.post(
                f"{self._base}/api/chat",
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            message = data.get("message", {})
            return ModelOutput(
                response_text=message.get("content", ""),
                finish_reason=data.get("done_reason", "stop"),
                token_usage={
                    "prompt_tokens": data.get("prompt_eval_count", 0),
                    "completion_tokens": data.get("eval_count", 0),
                    "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
                },
                metadata={"model": self._model, "backend": "ollama"},
            )
        except requests.ConnectionError:
            return self._error_output(
                "[Ollama not running — start it with: ollama serve]",
                "connection_refused",
            )
        except Exception as exc:
            logger.warning("Ollama completion failed: %s", exc)
            return self._error_output(f"[Meteor]: {exc}", str(exc))

    def stream(self, input: ModelInput) -> Iterator[str]:
        payload = self._build_payload(input, stream=True)
        try:
            resp = requests.post(
                f"{self._base}/api/chat",
                json=payload,
                timeout=180,
                stream=True,
            )
            resp.raise_for_status()
            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                message = chunk.get("message", {})
                token = message.get("content", "")
                if token:
                    yield token
                if chunk.get("done", False):
                    break
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
                names = [m["name"] for m in models]
                return {
                    "healthy": True,
                    "backend": "ollama",
                    "model": self._model,
                    "model_available": any(
                        self._model in name or name.startswith(f"{self._model}:")
                        for name in names
                    ),
                    "models": names,
                    "context_window": self._context_window,
                    "base_url": self._base,
                }
            return {"healthy": False, "backend": "ollama", "error": f"status {resp.status_code}"}
        except requests.ConnectionError:
            return {"healthy": False, "backend": "ollama", "error": "connection refused"}
        except Exception as exc:
            return {"healthy": False, "backend": "ollama", "error": str(exc)}

    def _build_payload(self, input: ModelInput, *, stream: bool) -> dict[str, Any]:
        temperature = input.temperature
        if input.metadata.get("task_mode"):
            temperature = resolve_temperature(self._profile, input.metadata)

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": self._build_messages(input),
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_ctx": self._context_window,
                "num_predict": input.max_tokens or self._max_tokens,
            },
        }
        if input.metadata.get("format") == "json":
            payload["format"] = "json"
        return payload

    def _build_messages(self, input: ModelInput) -> list[dict[str, str]]:
        if input.metadata.get("chat_messages"):
            return list(input.metadata["chat_messages"])

        messages: list[dict[str, str]] = []
        system = input.system_prompt or input.metadata.get("system_prompt", "")
        if system:
            messages.append({"role": "system", "content": system})

        for msg in input.context:
            role = msg.get("role", "user")
            if role not in ("system", "user", "assistant"):
                role = "user"
            messages.append({"role": role, "content": msg.get("content", "")})

        # Legacy assembled prompt fallback
        if input.prompt.startswith("System:"):
            return [{"role": "user", "content": input.prompt}]

        messages.append({"role": "user", "content": input.prompt})
        return messages

    def _error_output(self, text: str, error: str) -> ModelOutput:
        return ModelOutput(
            response_text=text,
            finish_reason="error",
            token_usage={"total_tokens": 0},
            metadata={"error": error, "model": self._model},
        )


def build_ollama_adapter(profile: ModelProfile) -> OllamaAdapter:
    return OllamaAdapter(profile)

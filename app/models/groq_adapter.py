"""Groq / OpenAI-compatible adapter — free, fast hosted inference.

Groq's LPU serves llama-3.1-8b-instant at ~750 tok/s and llama-3.3-70b-versatile
at ~275 tok/s on their free tier. The API is OpenAI-compatible, so this adapter
also drives Cerebras (`api.cerebras.ai/v1`), OpenRouter (`openrouter.ai/api/v1`),
and any other OpenAI-shaped endpoint by swapping `base_url`.

Reads the API key from the environment variable named in `profile.model_path`
suffix (`groq_llama3.1-8b-instant` → `GROQ_API_KEY`) or from the profile's
`api_key_env` metadata via `base_url` convention. Missing key → error output,
which the registry falls back on to Ollama.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Iterator

import requests

from app.config import ModelProfile
from app.models.contract import ModelAdapter, ModelInput, ModelOutput
from app.models.task_temperature import resolve_temperature

logger = logging.getLogger(__name__)


_BACKEND_ENV = {
    "groq": ("GROQ_API_KEY", "https://api.groq.com/openai/v1"),
    "cerebras": ("CEREBRAS_API_KEY", "https://api.cerebras.ai/v1"),
    "openrouter": ("OPENROUTER_API_KEY", "https://openrouter.ai/api/v1"),
    "together": ("TOGETHER_API_KEY", "https://api.together.xyz/v1"),
    "gemini_openai": ("GEMINI_API_KEY", "https://generativelanguage.googleapis.com/v1beta/openai"),
}


class OpenAICompatibleAdapter(ModelAdapter):
    """Drives any OpenAI /v1/chat/completions endpoint. Streams via SSE."""

    def __init__(self, profile: ModelProfile, *, backend_key: str) -> None:
        self._profile = profile
        self._backend_key = backend_key
        env_var, default_base = _BACKEND_ENV.get(backend_key, ("GROQ_API_KEY", ""))
        self._api_key = os.environ.get(env_var, "").strip()
        self._model = profile.model_path
        base = (profile.base_url or default_base).strip()
        self._base = base.rstrip("/") if base else default_base.rstrip("/")
        self._context_window = profile.context_window
        self._max_tokens = profile.max_tokens
        self._env_var = env_var

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _missing_key(self) -> ModelOutput:
        return ModelOutput(
            response_text=(
                f"[{self._backend_key}: no API key — set {self._env_var} to enable "
                f"free hosted inference; falling back to local model]"
            ),
            finish_reason="no_api_key",
            token_usage={"total_tokens": 0},
            metadata={"backend": self._backend_key, "error": "no_api_key"},
        )

    def complete(self, input: ModelInput) -> ModelOutput:
        if not self._api_key:
            return self._missing_key()

        payload = self._build_payload(input, stream=False)
        try:
            resp = requests.post(
                f"{self._base}/chat/completions",
                headers=self._headers(),
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            choice = (data.get("choices") or [{}])[0]
            message = choice.get("message", {}) or {}
            usage = data.get("usage", {}) or {}
            return ModelOutput(
                response_text=message.get("content", "") or "",
                finish_reason=choice.get("finish_reason", "stop") or "stop",
                token_usage={
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                },
                metadata={"backend": self._backend_key, "model": self._model},
            )
        except requests.HTTPError as exc:
            body = exc.response.text[:400] if exc.response is not None else ""
            logger.warning("%s completion failed: %s %s", self._backend_key, exc, body)
            return self._error(f"[{self._backend_key}: {exc.response.status_code if exc.response else '?'} {body}]", str(exc))
        except Exception as exc:
            logger.warning("%s completion failed: %s", self._backend_key, exc)
            return self._error(f"[{self._backend_key}: {exc}]", str(exc))

    def stream(self, input: ModelInput) -> Iterator[str]:
        if not self._api_key:
            yield self._missing_key().response_text
            return

        payload = self._build_payload(input, stream=True)
        try:
            resp = requests.post(
                f"{self._base}/chat/completions",
                headers=self._headers(),
                json=payload,
                timeout=180,
                stream=True,
            )
            resp.raise_for_status()
            for raw in resp.iter_lines(decode_unicode=True):
                if not raw or not raw.startswith("data:"):
                    continue
                data_str = raw[5:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                token = delta.get("content") or ""
                if token:
                    yield token
                if choices[0].get("finish_reason"):
                    break
        except requests.HTTPError as exc:
            body = exc.response.text[:400] if exc.response is not None else ""
            logger.warning("%s stream failed: %s %s", self._backend_key, exc, body)
            yield f"[{self._backend_key}: {exc.response.status_code if exc.response else '?'} {body}]"
        except Exception as exc:
            logger.warning("%s stream failed: %s", self._backend_key, exc)
            yield f"[{self._backend_key}: {exc}]"

    def health(self) -> dict:
        if not self._api_key:
            return {"healthy": False, "backend": self._backend_key, "error": f"missing {self._env_var}"}
        try:
            resp = requests.get(f"{self._base}/models", headers=self._headers(), timeout=5)
            healthy = resp.status_code == 200
            names: list[str] = []
            if healthy:
                data = resp.json().get("data", []) or []
                names = [m.get("id", "") for m in data if m.get("id")]
            return {
                "healthy": healthy,
                "backend": self._backend_key,
                "model": self._model,
                "model_available": self._model in names if names else healthy,
                "models": names[:20],
                "context_window": self._context_window,
                "base_url": self._base,
            }
        except Exception as exc:
            return {"healthy": False, "backend": self._backend_key, "error": str(exc)}

    def _build_payload(self, input: ModelInput, *, stream: bool) -> dict[str, Any]:
        temperature = input.temperature
        if input.metadata.get("task_mode"):
            temperature = resolve_temperature(self._profile, input.metadata)

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": self._build_messages(input),
            "stream": stream,
            "temperature": temperature,
            "max_tokens": input.max_tokens or self._max_tokens,
        }
        if input.metadata.get("format") == "json":
            payload["response_format"] = {"type": "json_object"}
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
        messages.append({"role": "user", "content": input.prompt})
        return messages

    def _error(self, text: str, err: str) -> ModelOutput:
        return ModelOutput(
            response_text=text,
            finish_reason="error",
            token_usage={"total_tokens": 0},
            metadata={"backend": self._backend_key, "error": err, "model": self._model},
        )


def build_openai_compatible_adapter(profile: ModelProfile, backend_key: str) -> OpenAICompatibleAdapter:
    return OpenAICompatibleAdapter(profile, backend_key=backend_key)

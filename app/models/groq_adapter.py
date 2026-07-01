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
import re
import threading
from typing import Any, Iterator

import httpx

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
    # Keyless free public endpoint — anyone with wifi can use it, no signup.
    "pollinations": ("POLLINATIONS_TOKEN", "https://text.pollinations.ai/openai"),
}

# Backends that do not require an API key — the adapter skips Authorization
# and never returns the "no_api_key" stub for these.
_KEYLESS_BACKENDS = {"pollinations"}

# Transient-failure retry policy for hosted endpoints (esp. keyless free ones).
_MAX_RETRIES = 3


def _backoff(attempt: int) -> None:
    import time
    time.sleep(min(0.5 * (2 ** attempt), 3.0))


# ── Shared HTTP client ──────────────────────────────────────────────────
# One process-wide httpx.Client with HTTP/2 + keepalive pool. Using a shared
# client means DNS resolution + TLS handshake + TCP setup happen once, not per
# request. HTTP/2 additionally multiplexes streams over the same socket, so a
# streaming SSE call and a completion call to the same host share a connection.
_CLIENT: httpx.Client | None = None
_CLIENT_LOCK = threading.Lock()

_STREAM_TIMEOUT = httpx.Timeout(180.0, connect=5.0, read=180.0)
_COMPLETE_TIMEOUT = httpx.Timeout(120.0, connect=5.0, read=120.0)
_HEALTH_TIMEOUT = httpx.Timeout(5.0, connect=5.0, read=5.0)


def get_http_client() -> httpx.Client:
    """Return the shared httpx.Client, building it on first use."""
    global _CLIENT
    if _CLIENT is None:
        with _CLIENT_LOCK:
            if _CLIENT is None:
                _CLIENT = httpx.Client(
                    http2=True,
                    limits=httpx.Limits(
                        max_keepalive_connections=32,
                        max_connections=64,
                        keepalive_expiry=60.0,
                    ),
                    timeout=_COMPLETE_TIMEOUT,
                    headers={"User-Agent": "Meteor/1.0"},
                    follow_redirects=True,
                )
    return _CLIENT


def close_http_client() -> None:
    """Close the shared client — called from the FastAPI lifespan shutdown."""
    global _CLIENT
    with _CLIENT_LOCK:
        if _CLIENT is not None:
            try:
                _CLIENT.close()
            except Exception:
                pass
            _CLIENT = None


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
        # Lazy-built keyless fallback (see _get_fallback).
        self._fallback: OpenAICompatibleAdapter | None = None

    def _get_fallback(self) -> OpenAICompatibleAdapter | None:
        """Return a keyless Pollinations fallback for transient upstream failures.
        None when already on Pollinations (no self-fallback loop)."""
        if self._backend_key == "pollinations":
            return None
        if self._fallback is None:
            fallback_profile = ModelProfile(
                backend="pollinations",
                model_path="openai-fast",
                context_window=32768,
                temperature=self._profile.temperature,
                max_tokens=self._max_tokens,
                wired=True,
                base_url="https://text.pollinations.ai/openai",
                role="fast",
            )
            self._fallback = OpenAICompatibleAdapter(fallback_profile, backend_key="pollinations")
        return self._fallback

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self._api_key:
            h["Authorization"] = f"Bearer {self._api_key}"
        return h

    def _keyless(self) -> bool:
        return self._backend_key in _KEYLESS_BACKENDS

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
        if not self._api_key and not self._keyless():
            return self._missing_key()

        payload = self._build_payload(input, stream=False)
        client = get_http_client()
        # Free/keyless endpoints (Pollinations) throw transient 5xx and the odd
        # empty completion under load. Retry a couple of times with backoff so a
        # flaky gateway doesn't surface as a blank chat reply.
        last_err = ""
        for attempt in range(_MAX_RETRIES):
            try:
                resp = client.post(
                    f"{self._base}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                    timeout=_COMPLETE_TIMEOUT,
                )
                if resp.status_code >= 500:
                    last_err = f"{resp.status_code} upstream error"
                    _backoff(attempt)
                    continue
                resp.raise_for_status()
                data = resp.json()
                choice = (data.get("choices") or [{}])[0]
                message = choice.get("message", {}) or {}
                usage = data.get("usage", {}) or {}
                text = message.get("content", "") or ""
                if not text.strip() and attempt < _MAX_RETRIES - 1:
                    last_err = "empty completion"
                    _backoff(attempt)
                    continue
                return ModelOutput(
                    response_text=text,
                    finish_reason=choice.get("finish_reason", "stop") or "stop",
                    token_usage={
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                        "total_tokens": usage.get("total_tokens", 0),
                    },
                    metadata={"backend": self._backend_key, "model": self._model},
                )
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code if exc.response is not None else None
                body = exc.response.text[:800] if exc.response is not None else ""
                logger.warning("%s completion failed: %s %s", self._backend_key, exc, body)
                fallback = self._get_fallback()
                if fallback and (status == 429 or (status and status >= 500)):
                    logger.info("%s → falling back to pollinations (status=%s)", self._backend_key, status)
                    return fallback.complete(input)
                return self._error(self._friendly_http_error(status, body), body)
            except Exception as exc:
                last_err = str(exc)
                logger.warning("%s completion failed (attempt %d): %s", self._backend_key, attempt + 1, exc)
                _backoff(attempt)
                continue
        return self._error(
            f"[{self._backend_key}: no response after {_MAX_RETRIES} attempts — {last_err or 'unknown error'}]",
            last_err,
        )

    def stream(self, input: ModelInput) -> Iterator[str]:
        if not self._api_key and not self._keyless():
            yield self._missing_key().response_text
            return

        payload = self._build_payload(input, stream=True)
        client = get_http_client()
        yielded_any = False
        try:
            with client.stream(
                "POST",
                f"{self._base}/chat/completions",
                headers=self._headers(),
                json=payload,
                timeout=_STREAM_TIMEOUT,
            ) as resp:
                resp.raise_for_status()
                for raw in resp.iter_lines():
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
                        yielded_any = True
                        yield token
                    if choices[0].get("finish_reason"):
                        break
            if not yielded_any:
                logger.warning("%s stream ended with no content tokens", self._backend_key)
                yield (
                    f"[{self._backend_key}: the model returned an empty response. "
                    "Try rephrasing or resending.]"
                )
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code if exc.response is not None else None
            body = ""
            try:
                body = exc.response.text[:800] if exc.response is not None else ""
            except Exception:
                body = ""
            logger.warning("%s stream failed: %s %s", self._backend_key, exc, body)
            # Transient upstream failures (rate limit, 5xx): silently retry on the
            # keyless Pollinations backend so the user gets an answer instead of
            # an error surface. Only kicks in when we haven't yielded any tokens.
            fallback = self._get_fallback()
            if fallback and not yielded_any and (status == 429 or (status and status >= 500)):
                logger.info("%s → falling back to pollinations (status=%s)", self._backend_key, status)
                yield from fallback.stream(input)
                return
            yield self._friendly_http_error(status, body)
        except Exception as exc:
            logger.warning("%s stream failed: %s", self._backend_key, exc)
            # Network / timeout / DNS: same failover as above.
            fallback = self._get_fallback()
            if fallback and not yielded_any:
                logger.info("%s → falling back to pollinations (network error)", self._backend_key)
                yield from fallback.stream(input)
                return
            yield f"[{self._backend_key} error: something went wrong talking to the model. Try again in a moment.]"

    def _friendly_http_error(self, status: int | None, body: str) -> str:
        """Turn a raw HTTP error body into a short, human-readable message
        instead of leaking the provider's JSON payload into the chat."""
        message = ""
        try:
            parsed = json.loads(body)
            message = (parsed.get("error") or {}).get("message", "")
        except (json.JSONDecodeError, AttributeError):
            pass

        if status == 429:
            retry_hint = ""
            m = re.search(r"try again in ([\d.]+)s", message, re.IGNORECASE)
            if m:
                retry_hint = f" Retry in ~{float(m.group(1)):.0f}s."
            return (
                f"[{self._backend_key}: rate limit reached.{retry_hint} "
                "Switch to a different model/profile or wait a moment and resend.]"
            )
        if status == 401:
            return f"[{self._backend_key}: authentication failed — check {self._env_var}.]"
        if status and status >= 500:
            return f"[{self._backend_key}: upstream server error ({status}). Try again shortly.]"
        if message:
            return f"[{self._backend_key}: {message}]"
        return f"[{self._backend_key}: request failed ({status or '?'}).]"

    def health(self) -> dict:
        if not self._api_key and not self._keyless():
            return {"healthy": False, "backend": self._backend_key, "error": f"missing {self._env_var}"}
        try:
            resp = get_http_client().get(
                f"{self._base}/models",
                headers=self._headers(),
                timeout=_HEALTH_TIMEOUT,
            )
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

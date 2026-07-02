"""Tests for the model adapter layer.

Verifies: adapter contract, registry factory, health checks, error handling.
Does NOT test actual inference (requires a real GGUF model file).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import MeteorConfig, ModelProfile
from app.models.contract import ModelAdapter, ModelInput, ModelOutput
from app.models.registry import ModelRegistry


CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "meteor.yaml"


def test_model_input_defaults() -> None:
    inp = ModelInput(prompt="test")
    assert inp.prompt == "test"
    assert inp.max_tokens == 512
    assert inp.temperature == 0.7
    assert inp.context == []
    assert inp.metadata == {}


def test_model_output_defaults() -> None:
    out = ModelOutput(response_text="test", finish_reason="stop")
    assert out.response_text == "test"
    assert out.finish_reason == "stop"
    assert out.token_usage == {}
    assert out.metadata == {}


def test_model_adapter_is_abstract() -> None:
    with pytest.raises(TypeError):
        ModelAdapter()


def test_registry_lists_profiles() -> None:
    """Default config ships hosted-only profiles (Meteor is an MCP kit, not a
    local-inference runtime); the keyless Pollinations default is always
    present, and any Groq/Cerebras/Gemini profiles are optional key-gated."""
    config = MeteorConfig.load(CONFIG_PATH)
    registry = ModelRegistry(config, Path(__file__).resolve().parent.parent)
    profiles = registry.list_profiles()
    assert "pollinations-free" in profiles
    assert config.models.default_profile in profiles


def test_registry_get_adapter_raises_on_missing_profile() -> None:
    config = MeteorConfig.load(CONFIG_PATH)
    registry = ModelRegistry(config, Path(__file__).resolve().parent.parent)
    with pytest.raises(ValueError, match="not found"):
        registry.get_adapter("nonexistent-profile")


def test_registry_get_adapter_raises_on_missing_model_file(tmp_path) -> None:
    """The llama.cpp adapter still errors cleanly when its model file is
    missing — verified via a synthetic config, since the default ships hosted
    profiles only."""
    config = MeteorConfig.load(CONFIG_PATH)
    config.models.profiles["llama-missing"] = ModelProfile(
        backend="llama_cpp",
        model_path="nonexistent.gguf",
        context_window=4096,
        temperature=0.7,
        temperature_structured=0.2,
        temperature_creative=0.8,
        max_tokens=512,
        wired=True,
    )
    registry = ModelRegistry(config, Path(__file__).resolve().parent.parent)
    with pytest.raises((FileNotFoundError, ImportError)):
        registry.get_adapter("llama-missing")


def test_model_profile_has_required_fields() -> None:
    config = MeteorConfig.load(CONFIG_PATH)
    profile = config.models.profiles[config.models.default_profile]
    hosted = ("pollinations", "groq", "cerebras", "gemini_openai", "together", "openrouter")
    assert profile.backend in ("llama_cpp", "ollama", *hosted)
    # Local llama_cpp needs a .gguf path; ollama/hosted just name a model.
    assert profile.model_path.endswith(".gguf") or profile.backend != "llama_cpp"
    assert profile.context_window > 0
    assert 0.0 <= profile.temperature <= 2.0
    assert profile.max_tokens > 0


class MockAdapter(ModelAdapter):
    def complete(self, input: ModelInput) -> ModelOutput:
        return ModelOutput(
            response_text=f"mock: {input.prompt}",
            finish_reason="stop",
            token_usage={"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
        )

    def stream(self, input: ModelInput):
        yield "mock"
        yield " "
        yield "stream"

    def health(self) -> dict:
        return {"healthy": True, "backend": "mock"}


def test_mock_adapter_complete() -> None:
    adapter = MockAdapter()
    result = adapter.complete(ModelInput(prompt="hello"))
    assert result.response_text == "mock: hello"
    assert result.finish_reason == "stop"
    assert result.token_usage["total_tokens"] == 3


def test_mock_adapter_stream() -> None:
    adapter = MockAdapter()
    tokens = list(adapter.stream(ModelInput(prompt="hello")))
    assert tokens == ["mock", " ", "stream"]


def test_mock_adapter_health() -> None:
    adapter = MockAdapter()
    health = adapter.health()
    assert health["healthy"] is True
    assert health["backend"] == "mock"

"""Tests for Ollama adapter payload construction and task temperature."""

from __future__ import annotations

from app.config import ModelProfile
from app.models.contract import ModelInput
from app.models.ollama_adapter import OllamaAdapter
from app.models.task_temperature import resolve_temperature
from app.runtime.depth_context import _parse_intent_json
from app.models.contract import ModelOutput


def _profile(**overrides) -> ModelProfile:
    base = dict(
        backend="ollama",
        model_path="llama3.1:8b",
        context_window=8192,
        temperature=0.7,
        max_tokens=1024,
        wired=True,
        base_url="http://localhost:11434",
        temperature_structured=0.2,
        temperature_creative=0.8,
        role="heavy",
    )
    base.update(overrides)
    return ModelProfile(**base)


def test_resolve_temperature_task_modes() -> None:
    profile = _profile()
    assert resolve_temperature(profile, {"task_mode": "structured"}) == 0.2
    assert resolve_temperature(profile, {"task_mode": "creative"}) == 0.8
    assert resolve_temperature(profile, {"temperature": 0.55}) == 0.55


def test_ollama_build_payload_uses_chat_and_num_ctx() -> None:
    adapter = OllamaAdapter(_profile())
    payload = adapter._build_payload(
        ModelInput(
            prompt="dig into the network",
            system_prompt="You are Meteor.",
            context=[{"role": "user", "content": "hello"}],
            metadata={"task_mode": "structured"},
        ),
        stream=True,
    )
    assert payload["model"] == "llama3.1:8b"
    assert payload["stream"] is True
    assert payload["options"]["num_ctx"] == 8192
    assert payload["options"]["temperature"] == 0.2
    assert payload["messages"][0]["role"] == "system"
    assert payload["messages"][-1]["content"] == "dig into the network"


def test_parse_intent_json_from_model_output() -> None:
    output = ModelOutput(
        response_text='{"intent": "scan", "args": {"target": "192.168.1.1"}, "reason": "gateway"}',
        finish_reason="stop",
    )
    parsed = _parse_intent_json(output)
    assert parsed is not None
    assert parsed["intent"] == "scan"
    assert parsed["args"]["target"] == "192.168.1.1"

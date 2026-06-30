"""Tests for LLM intent fallback, rate limiter, and depth session store."""

from __future__ import annotations

from dataclasses import asdict

import pytest

from app.config import ModelProfile
from app.gui.intent_llm import _llm_payload_to_intent, _parse_llm_json, resolve_intent
from app.models.contract import ModelAdapter, ModelInput, ModelOutput
from app.runtime.depth_session_store import DepthSessionStore, SessionFindings, StoredDepthSession
from app.runtime.rate_limiter import OpClass, RateLimitConfig, SessionRateLimiter


class _StubModel(ModelAdapter):
    def __init__(self, response: str) -> None:
        self._response = response

    def complete(self, input: ModelInput) -> ModelOutput:
        return ModelOutput(response_text=self._response, finish_reason="stop")

    def stream(self, input: ModelInput):
        yield self._response

    def health(self) -> dict:
        return {"healthy": True}


class _StubRegistry:
    def __init__(self, model: ModelAdapter) -> None:
        self._model = model

    def get_adapter(self, name: str | None = None) -> ModelAdapter:
        return self._model

    def resolve_for_request(self, metadata: dict | None = None) -> ModelAdapter:
        return self._model


def test_parse_llm_json_intent() -> None:
    data = _parse_llm_json(
        '{"action": "port_scan", "target": "192.168.1.1", "params": {"port": 445}, "reason": "check smb"}'
    )
    assert data is not None
    assert data["action"] == "port_scan"


def test_llm_payload_maps_vuln_check_to_scan() -> None:
    intent = _llm_payload_to_intent(
        {"action": "vuln_check", "target": "", "params": {"service": "smb"}, "reason": "smb share"},
        default_gateway="192.168.1.1",
        default_cidr="192.168.1.0/24",
        user_text="see if that SMB share is vulnerable",
    )
    assert intent is not None
    assert intent.command == "scan"


def test_resolve_intent_llm_fallback(tmp_path) -> None:
    registry = _StubRegistry(
        _StubModel(
            '{"action": "service_enum", "target": "192.168.1.5", "params": {"port": 445}, "reason": "port check"}'
        )
    )
    cmd, args, routed = resolve_intent(
        "maybe check what's running on port 445",
        default_gateway="192.168.1.1",
        default_cidr="192.168.1.0/24",
        model_registry=registry,
    )
    assert cmd == "scan"
    assert routed is not None
    assert args.get("port") == 445


def test_rate_limiter_blocks_second_deep_op() -> None:
    limiter = SessionRateLimiter(RateLimitConfig(max_concurrent_deep=1, max_quick_per_minute=10))
    assert limiter.acquire("s1", OpClass.DEEP).allowed
    assert not limiter.acquire("s1", OpClass.DEEP).allowed
    limiter.release("s1", OpClass.DEEP)
    assert limiter.acquire("s1", OpClass.DEEP).allowed
    limiter.release("s1", OpClass.DEEP)


def test_rate_limiter_caps_quick_ops() -> None:
    limiter = SessionRateLimiter(RateLimitConfig(max_quick_per_minute=2))
    assert limiter.acquire("s2", OpClass.QUICK).allowed
    assert limiter.acquire("s2", OpClass.QUICK).allowed
    assert not limiter.acquire("s2", OpClass.QUICK).allowed


def test_depth_session_store_persists(tmp_path) -> None:
    store = DepthSessionStore(base_dir=tmp_path)
    stored = StoredDepthSession(
        session_id="gui-test",
        max_depth=3,
        steps=[{"name": "probe", "output": "445 open", "summary": "SMB on .1"}],
        findings=asdict(SessionFindings(gateway="192.168.1.1", top_services=["smb:445"])),
    )
    store.save(stored)
    loaded = store.load("gui-test")
    assert loaded is not None
    assert loaded.findings["gateway"] == "192.168.1.1"
    block = store.context_block("gui-test")
    assert "SMB" in block or "smb" in block

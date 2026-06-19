from __future__ import annotations

from app.runtime.contract import RuntimeRequest, RuntimeResponse, RuntimeStatus
from app.runtime.orchestrator import build_orchestrator


def test_runtime_request_is_dataclass() -> None:
    req = RuntimeRequest(prompt="hello")
    assert req.prompt == "hello"
    assert isinstance(req.metadata, dict)


def test_runtime_response_is_dataclass() -> None:
    resp = RuntimeResponse(
        response_text="test",
        status=RuntimeStatus.NOT_IMPLEMENTED,
    )
    assert resp.status == RuntimeStatus.NOT_IMPLEMENTED
    assert isinstance(resp.evidence, list)
    assert isinstance(resp.metadata, dict)


def test_runtime_status_values_are_strings() -> None:
    for status in RuntimeStatus:
        assert isinstance(status.value, str)


def test_orchestrator_handle_returns_not_implemented() -> None:
    orchestrator = build_orchestrator()
    response = orchestrator.handle(RuntimeRequest(prompt="test"))
    assert response.status == RuntimeStatus.NOT_IMPLEMENTED
    assert "not wired" in response.response_text.lower()


def test_orchestrator_handle_includes_policy_metadata() -> None:
    orchestrator = build_orchestrator()
    response = orchestrator.handle(RuntimeRequest(prompt="test"))
    assert "policy_action" in response.metadata
    assert response.metadata["policy_action"] == "runtime_invoke"


def test_orchestrator_model_wired_is_false() -> None:
    orchestrator = build_orchestrator()
    response = orchestrator.handle(RuntimeRequest(prompt="test"))
    assert response.metadata.get("model_wired") is False

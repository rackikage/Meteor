from __future__ import annotations

from app.runtime.contract import RuntimeRequest, RuntimeResponse, RuntimeStatus


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


def test_orchestrator_request_fields() -> None:
    from app.runtime.orchestrator import OrchestratorRequest
    req = OrchestratorRequest(prompt="test")
    assert req.prompt == "test"
    assert req.max_tokens == 512
    assert req.temperature == 0.7
    assert req.max_tool_iterations == 5


def test_orchestrator_response_fields() -> None:
    from app.runtime.orchestrator import OrchestratorResponse
    resp = OrchestratorResponse(
        session_id="s1",
        response_text="ok",
        finish_reason="stop",
    )
    d = resp.to_dict()
    assert d["session_id"] == "s1"
    assert d["response_text"] == "ok"
    assert "tool_results" in d
    assert "duration_ms" in d

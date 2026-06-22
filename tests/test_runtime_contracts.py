from __future__ import annotations

from pathlib import Path

from app.bootstrap import resolve_repo_path
from app.config import MeteorConfig
from app.context.builder import ContextBuilder
from app.memory.sqlite_adapter import SQLiteMemoryAdapter
from app.models.null_adapter import DisabledModelAdapter
from app.observability.memory_adapter import InMemoryObservabilityAdapter
from app.policy.engine import build_policy_engine
from app.retrieval.null_adapter import NullRetrievalAdapter
from app.runtime.contract import RuntimeRequest, RuntimeResponse, RuntimeStatus
from app.runtime.orchestrator import RuntimeAdapters, RuntimeOrchestrator

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "meteor.yaml"


def _orchestrator(tmp_path: Path) -> RuntimeOrchestrator:
    config = MeteorConfig.load(CONFIG_PATH)
    engine = build_policy_engine(config, repo_root=CONFIG_PATH.parent.parent)
    profile_name = config.models.default_profile
    profile = config.models.profiles[profile_name]
    adapters = RuntimeAdapters(
        model=DisabledModelAdapter(profile_name, profile, str(resolve_repo_path(CONFIG_PATH.parent.parent, profile.model_path))),
        retrieval=NullRetrievalAdapter(),
        memory=SQLiteMemoryAdapter(tmp_path / "memory.db"),
        observability=InMemoryObservabilityAdapter(),
        context_builder=ContextBuilder(),
    )
    return RuntimeOrchestrator(policy_engine=engine, adapters=adapters)


def test_runtime_request_is_dataclass() -> None:
    req = RuntimeRequest(prompt="hello")
    assert req.prompt == "hello"
    assert req.session_id == "default"
    assert isinstance(req.metadata, dict)


def test_runtime_response_is_dataclass() -> None:
    resp = RuntimeResponse(
        response_text="test",
        status=RuntimeStatus.DEGRADED,
    )
    assert resp.status == RuntimeStatus.DEGRADED
    assert isinstance(resp.evidence, list)
    assert isinstance(resp.metadata, dict)


def test_runtime_status_values_are_strings() -> None:
    for status in RuntimeStatus:
        assert isinstance(status.value, str)


def test_orchestrator_handle_runs_pipeline_with_disabled_model(tmp_path) -> None:
    orchestrator = _orchestrator(tmp_path)
    response = orchestrator.handle(RuntimeRequest(prompt="test", session_id="s1"))
    assert response.status == RuntimeStatus.DEGRADED
    assert "pipeline executed" in response.response_text.lower()


def test_orchestrator_handle_includes_policy_metadata(tmp_path) -> None:
    orchestrator = _orchestrator(tmp_path)
    response = orchestrator.handle(RuntimeRequest(prompt="test", session_id="s1"))
    assert response.metadata["runtime_wired"] is True
    assert response.metadata["model_finish_reason"] == "model_disabled"
    assert len(response.metadata["policy_trace"]) >= 4


def test_orchestrator_component_wiring_flags(tmp_path) -> None:
    orchestrator = _orchestrator(tmp_path)
    response = orchestrator.handle(RuntimeRequest(prompt="test", session_id="s1"))
    assert response.metadata["model_wired"] is False
    assert response.metadata["retrieval_wired"] is False
    assert response.metadata["memory_wired"] is True


def test_orchestrator_writes_memory_after_request(tmp_path) -> None:
    orchestrator = _orchestrator(tmp_path)
    first = orchestrator.handle(RuntimeRequest(prompt="first", session_id="s1"))
    second = orchestrator.handle(RuntimeRequest(prompt="second", session_id="s1"))
    assert first.status == RuntimeStatus.DEGRADED
    assert second.metadata["context_item_count"] >= 1


def test_runtime_health_reports_wired_boundaries(tmp_path) -> None:
    orchestrator = _orchestrator(tmp_path)
    health = orchestrator.health()
    assert health["runtime_wired"] is True
    assert health["model"]["wired"] is False
    assert health["memory"]["wired"] is True

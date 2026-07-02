"""Integration tests — end-to-end runtime workflow.

Verifies: full runtime initialization, policy → model → memory → retrieval → evidence flow,
health checks across all components, API endpoints.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.bootstrap import bootstrap
from app.config import MeteorConfig
from app.evidence.tracker import EvidenceTracker
from app.memory.contract import MemoryEntry, MemoryType
from app.memory.sqlite_adapter import build_sqlite_memory_adapter
from app.models.registry import ModelRegistry
from app.observability.sqlite_adapter import build_sqlite_observability_adapter
from app.retrieval.contract import RetrievalQuery
from app.retrieval.sqlite_adapter import build_sqlite_retrieval_adapter
from app.storage.sqlite_adapter import build_sqlite_adapter


CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "meteor.yaml"


@pytest.fixture
def runtime_components(tmp_path):
    """Initialize all runtime components for integration testing."""
    config = MeteorConfig.load(CONFIG_PATH)
    config.storage.paths.memory = str(tmp_path / "test_memory.db")
    config.storage.paths.audit = str(tmp_path / "test_audit.db")
    config.storage.paths.index_meta = str(tmp_path / "test_index_meta.db")

    storage = build_sqlite_adapter(config.storage, tmp_path)
    memory = build_sqlite_memory_adapter(storage)
    retrieval = build_sqlite_retrieval_adapter(storage)
    observability = build_sqlite_observability_adapter(
        storage, log_level="DEBUG", audit_enabled=True
    )
    evidence_tracker = EvidenceTracker()

    observability.register_health_check("storage", storage.health)
    observability.register_health_check("memory", memory.health)
    observability.register_health_check("retrieval", retrieval.health)

    yield {
        "config": config,
        "storage": storage,
        "memory": memory,
        "retrieval": retrieval,
        "observability": observability,
        "evidence_tracker": evidence_tracker,
        "repo_root": tmp_path,
    }

    storage.close()


def test_full_runtime_initialization(runtime_components) -> None:
    """Test that all runtime components initialize successfully."""
    assert runtime_components["storage"].health()["healthy"] is True
    assert runtime_components["memory"].health()["healthy"] is True
    assert runtime_components["retrieval"].health()["healthy"] is True
    assert runtime_components["observability"].health().healthy is True


def test_conversation_memory_workflow(runtime_components) -> None:
    """Test a full conversation memory workflow."""
    memory = runtime_components["memory"]

    user_msg = MemoryEntry(
        memory_type=MemoryType.CONVERSATION,
        content="What is machine learning?",
        session_id="test-session",
        timestamp=datetime.now(timezone.utc).isoformat(),
        metadata={"role": "user"},
    )
    memory.write(user_msg)

    assistant_msg = MemoryEntry(
        memory_type=MemoryType.CONVERSATION,
        content="Machine learning is a subset of AI...",
        session_id="test-session",
        timestamp=datetime.now(timezone.utc).isoformat(),
        metadata={"role": "assistant"},
    )
    memory.write(assistant_msg)

    history = memory.read("test-session", MemoryType.CONVERSATION)
    assert len(history) == 2
    assert history[0].metadata["role"] == "user"
    assert history[1].metadata["role"] == "assistant"


def test_retrieval_and_evidence_workflow(runtime_components) -> None:
    """Test document indexing, retrieval, and evidence tracking."""
    retrieval = runtime_components["retrieval"]
    evidence_tracker = runtime_components["evidence_tracker"]

    docs = [
        {
            "source": "https://example.com/ml-guide",
            "content": "Machine learning is a subset of artificial intelligence that enables systems to learn from data.",
            "metadata": {"category": "ai"},
        },
        {
            "source": "https://example.com/dl-guide",
            "content": "Deep learning uses neural networks with many layers to model complex patterns.",
            "metadata": {"category": "ai"},
        },
    ]
    retrieval.index(docs)

    query = RetrievalQuery(query_text="machine learning", top_k=2)
    result = retrieval.query(query)

    assert len(result.documents) > 0

    claim = evidence_tracker.annotate_response_with_evidence(
        response_text="Machine learning is a subset of AI.",
        retrieved_documents=result.documents,
    )

    assert claim.has_evidence
    assert claim.confidence in ("high", "medium", "low")


def test_policy_audit_workflow(runtime_components) -> None:
    """Test policy decision auditing."""
    from app.observability.contract import AuditEntry

    observability = runtime_components["observability"]

    audit_entry = AuditEntry(
        event="policy_check",
        layer="policy",
        subject="runtime",
        action="invoke",
        decision="allow",
        timestamp=datetime.now(timezone.utc).isoformat(),
        metadata={"reason": "test"},
    )
    observability.audit(audit_entry)

    entries = observability.get_audit_log(limit=10)
    assert len(entries) == 1
    assert entries[0].event == "policy_check"
    assert entries[0].decision == "allow"


def test_cross_session_memory(runtime_components) -> None:
    """Test memory persistence across sessions."""
    memory = runtime_components["memory"]

    session1_entry = MemoryEntry(
        memory_type=MemoryType.EPISODIC,
        content="User prefers dark mode",
        session_id="session-1",
        timestamp=datetime.now(timezone.utc).isoformat(),
        metadata={"event_type": "preference"},
    )
    memory.write(session1_entry)

    session2_entry = MemoryEntry(
        memory_type=MemoryType.EPISODIC,
        content="User asked about machine learning",
        session_id="session-2",
        timestamp=datetime.now(timezone.utc).isoformat(),
        metadata={"event_type": "query"},
    )
    memory.write(session2_entry)

    session1_memory = memory.read("session-1", MemoryType.EPISODIC)
    session2_memory = memory.read("session-2", MemoryType.EPISODIC)

    assert len(session1_memory) == 1
    assert len(session2_memory) == 1
    assert session1_memory[0].content != session2_memory[0].content


def test_health_aggregation(runtime_components) -> None:
    """Test that health checks aggregate across all components."""
    observability = runtime_components["observability"]

    health = observability.health()

    assert health.healthy is True
    assert "components" in health.metadata
    assert "storage" in health.metadata["components"]
    assert "memory" in health.metadata["components"]
    assert "retrieval" in health.metadata["components"]


def test_model_registry_initialization(tmp_path) -> None:
    """Model registry initializes with hosted-only default profiles — Meteor's
    MCP kit does not ship local inference in the default config."""
    config = MeteorConfig.load(CONFIG_PATH)
    registry = ModelRegistry(config, tmp_path)

    profiles = registry.list_profiles()
    assert "pollinations-free" in profiles
    assert config.models.default_profile in profiles


def test_bootstrap_integration() -> None:
    """Test that bootstrap loads config and resolves paths correctly."""
    result = bootstrap()

    assert result.config.app.name == "Meteor"
    assert result.config.app.local_first is True
    assert result.repo_root.exists()
    assert result.default_model_path.suffix in (".gguf", "") or result.default_model_path.name == "llama3.2"


def test_full_rag_workflow(runtime_components) -> None:
    """Test a complete RAG (Retrieval-Augmented Generation) workflow."""
    retrieval = runtime_components["retrieval"]
    memory = runtime_components["memory"]
    evidence_tracker = runtime_components["evidence_tracker"]

    docs = [
        {
            "source": "https://docs.python.org/3/tutorial",
            "content": "Python is an easy to learn, powerful programming language. It has efficient high-level data structures and a simple but effective approach to object-oriented programming.",
            "metadata": {"topic": "python"},
        },
        {
            "source": "https://docs.python.org/3/library",
            "content": "The Python standard library provides a wide range of modules for common programming tasks.",
            "metadata": {"topic": "python"},
        },
    ]
    retrieval.index(docs)

    user_query = "What is Python?"
    query = RetrievalQuery(query_text=user_query, top_k=2)
    retrieval_result = retrieval.query(query)

    assert len(retrieval_result.documents) > 0

    response_text = "Python is a powerful, easy-to-learn programming language with efficient high-level data structures."

    claim = evidence_tracker.annotate_response_with_evidence(
        response_text=response_text,
        retrieved_documents=retrieval_result.documents,
        metadata={"query": user_query},
    )

    assert claim.has_evidence
    assert len(claim.evidence) > 0

    conversation_entry = MemoryEntry(
        memory_type=MemoryType.CONVERSATION,
        content=f"Q: {user_query}\nA: {response_text}",
        session_id="rag-session",
        timestamp=datetime.now(timezone.utc).isoformat(),
        metadata={"role": "assistant", "has_evidence": claim.has_evidence},
    )
    memory.write(conversation_entry)

    history = memory.read("rag-session", MemoryType.CONVERSATION)
    assert len(history) == 1
    assert "Python" in history[0].content


def test_project_memory_persistence(runtime_components) -> None:
    """Test project-level memory persistence."""
    memory = runtime_components["memory"]

    settings_entry = MemoryEntry(
        memory_type=MemoryType.PROJECT,
        content='{"theme": "dark", "language": "en", "notifications": true}',
        session_id="any-session",
        timestamp=datetime.now(timezone.utc).isoformat(),
        metadata={"project_name": "my-app", "key": "settings"},
    )
    memory.write(settings_entry)

    project_memory = memory.read("any-session", MemoryType.PROJECT)
    assert len(project_memory) == 1
    assert project_memory[0].metadata["project_name"] == "my-app"
    assert project_memory[0].metadata["key"] == "settings"


def test_correction_memory(runtime_components) -> None:
    """Test correction memory for user feedback."""
    memory = runtime_components["memory"]

    correction = MemoryEntry(
        memory_type=MemoryType.CORRECTION,
        content="Use 'Hello' instead of 'Hi' for formal contexts",
        session_id="correction-session",
        timestamp=datetime.now(timezone.utc).isoformat(),
        metadata={
            "original": "Hi there!",
            "reason": "User prefers formal tone",
        },
    )
    memory.write(correction)

    corrections = memory.read("correction-session", MemoryType.CORRECTION)
    assert len(corrections) == 1
    assert corrections[0].metadata["original"] == "Hi there!"
    assert "formal" in corrections[0].metadata["reason"]

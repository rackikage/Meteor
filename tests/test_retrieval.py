"""Tests for the retrieval adapter layer.

Verifies: SQLite retrieval adapter, document indexing, keyword search, hybrid ranking.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import MeteorConfig
from app.retrieval.contract import RetrievalAdapter, RetrievalQuery
from app.retrieval.sqlite_adapter import SQLiteRetrievalAdapter, build_sqlite_retrieval_adapter
from app.storage.sqlite_adapter import build_sqlite_adapter


CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "meteor.yaml"


@pytest.fixture
def retrieval_adapter(tmp_path):
    """Create a temporary retrieval adapter for testing."""
    config = MeteorConfig.load(CONFIG_PATH)
    config.storage.paths.memory = str(tmp_path / "test_memory.db")
    config.storage.paths.audit = str(tmp_path / "test_audit.db")
    config.storage.paths.index_meta = str(tmp_path / "test_index_meta.db")
    storage = build_sqlite_adapter(config.storage, tmp_path)
    adapter = build_sqlite_retrieval_adapter(storage)
    yield adapter
    storage.close()


def test_retrieval_adapter_is_abstract() -> None:
    with pytest.raises(TypeError):
        RetrievalAdapter()


def test_index_documents(retrieval_adapter: SQLiteRetrievalAdapter) -> None:
    docs = [
        {"source": "doc1.txt", "content": "The quick brown fox jumps over the lazy dog."},
        {"source": "doc2.txt", "content": "Machine learning is a subset of artificial intelligence."},
    ]
    retrieval_adapter.index(docs)

    health = retrieval_adapter.health()
    assert health["document_count"] >= 2


def test_keyword_search(retrieval_adapter: SQLiteRetrievalAdapter) -> None:
    docs = [
        {"source": "doc1.txt", "content": "Python is a programming language. It is widely used for web development."},
        {"source": "doc2.txt", "content": "JavaScript runs in the browser. It is also used for server-side development."},
        {"source": "doc3.txt", "content": "Rust is a systems programming language. It focuses on safety and performance."},
    ]
    retrieval_adapter.index(docs)

    query = RetrievalQuery(query_text="programming language", top_k=2)
    result = retrieval_adapter.query(query)

    assert len(result.documents) > 0
    assert any("programming" in doc.content.lower() for doc in result.documents)


def test_search_with_top_k(retrieval_adapter: SQLiteRetrievalAdapter) -> None:
    docs = [
        {"source": f"doc{i}.txt", "content": f"Document {i} about machine learning and AI."}
        for i in range(10)
    ]
    retrieval_adapter.index(docs)

    query = RetrievalQuery(query_text="machine learning", top_k=3)
    result = retrieval_adapter.query(query)

    assert len(result.documents) <= 3


def test_search_with_metadata_filters(retrieval_adapter: SQLiteRetrievalAdapter) -> None:
    docs = [
        {"source": "doc1.txt", "content": "Python tutorial", "metadata": {"category": "programming", "level": "beginner"}},
        {"source": "doc2.txt", "content": "Advanced Python patterns", "metadata": {"category": "programming", "level": "advanced"}},
        {"source": "doc3.txt", "content": "Machine learning basics", "metadata": {"category": "ai", "level": "beginner"}},
    ]
    retrieval_adapter.index(docs)

    query = RetrievalQuery(
        query_text="Python",
        top_k=10,
        metadata_filters={"level": "beginner"},
    )
    result = retrieval_adapter.query(query)

    assert all(doc.metadata.get("level") == "beginner" for doc in result.documents)


def test_search_empty_index(retrieval_adapter: SQLiteRetrievalAdapter) -> None:
    query = RetrievalQuery(query_text="test", top_k=5)
    result = retrieval_adapter.query(query)

    assert len(result.documents) == 0


def test_chunking_large_document(retrieval_adapter: SQLiteRetrievalAdapter) -> None:
    large_content = "This is a sentence. " * 200
    docs = [{"source": "large.txt", "content": large_content}]
    retrieval_adapter.index(docs)

    health = retrieval_adapter.health()
    assert health["document_count"] >= 1


def test_retrieval_health(retrieval_adapter: SQLiteRetrievalAdapter) -> None:
    health = retrieval_adapter.health()
    assert health["healthy"] is True
    assert health["backend"] == "sqlite"
    assert "keyword" in health["search_types"]
    assert "hybrid" in health["search_types"]
    assert health["document_count"] >= 0


def test_search_returns_scores(retrieval_adapter: SQLiteRetrievalAdapter) -> None:
    docs = [
        {"source": "doc1.txt", "content": "Python programming language tutorial"},
        {"source": "doc2.txt", "content": "JavaScript web development guide"},
    ]
    retrieval_adapter.index(docs)

    query = RetrievalQuery(query_text="Python programming", top_k=2)
    result = retrieval_adapter.query(query)

    assert len(result.documents) > 0
    assert all(doc.score >= 0 for doc in result.documents)

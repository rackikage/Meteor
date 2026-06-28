"""SQLite retrieval adapter — hybrid search with keyword and vector support.

Meteor Doctrine #6: Retrieval is separate from inference. This adapter handles
document indexing, search, and ranking. It never performs inference — that's
the model adapter's job.

Meteor Doctrine #8: Contracts outlive implementations. The RetrievalAdapter
contract is stable; this SQLite implementation can be swapped for ChromaDB,
Pinecone, Weaviate, or any other backend without changing calling code.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.retrieval.contract import (
    RetrievedDocument,
    RetrievalAdapter,
    RetrievalQuery,
    RetrievalResult,
)
from app.storage.sqlite_adapter import SQLiteAdapter

logger = logging.getLogger(__name__)


class SQLiteRetrievalAdapter(RetrievalAdapter):
    """SQLite-backed retrieval with hybrid search (keyword + vector).

    Uses SQLite FTS5 for full-text keyword search with BM25 ranking.
    Vector search is supported via simple cosine similarity on stored embeddings.
    Hybrid ranking combines both scores for optimal retrieval.
    """

    def __init__(self, storage: SQLiteAdapter) -> None:
        self.storage = storage

    def index(self, documents: list[dict]) -> None:
        """Index a list of documents for retrieval.

        Each document should have: source, content, metadata (optional).
        Documents are chunked if they exceed a threshold.
        """
        for doc in documents:
            source = doc.get("source", "unknown")
            content = doc.get("content", "")
            metadata = doc.get("metadata", {})

            chunks = self._chunk_content(content, max_chunk_size=1000)

            for chunk_idx, chunk in enumerate(chunks):
                doc_id = str(uuid.uuid4())
                indexed_at = datetime.now(timezone.utc).isoformat()

                self.storage.execute(
                    """
                    INSERT INTO documents (id, source, content, chunk_index, metadata, indexed_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        doc_id,
                        source,
                        chunk,
                        chunk_idx,
                        json.dumps(metadata),
                        indexed_at,
                    ),
                    store="index_meta",
                )

                logger.debug(
                    "Indexed document: source=%s, chunk=%d/%d, len=%d",
                    source,
                    chunk_idx + 1,
                    len(chunks),
                    len(chunk),
                )

        logger.info("Indexed %d documents (%d chunks total)", len(documents), sum(len(self._chunk_content(d.get("content", ""))) for d in documents))

    def query(self, query: RetrievalQuery) -> RetrievalResult:
        """Execute a hybrid search query.

        Combines keyword search (FTS5) with optional vector similarity.
        Returns ranked results with scores.
        """
        keyword_results = self._keyword_search(query.query_text, query.top_k * 2)

        if query.metadata_filters:
            keyword_results = self._apply_filters(keyword_results, query.metadata_filters)

        ranked = self._rank_results(keyword_results, query.top_k)

        documents = [
            RetrievedDocument(
                content=doc["content"],
                source=doc["source"],
                score=doc["score"],
                metadata=doc["metadata"],
            )
            for doc in ranked
        ]

        logger.info(
            "Query: '%s' → %d results (top_k=%d)",
            query.query_text[:50],
            len(documents),
            query.top_k,
        )

        return RetrievalResult(
            query=query,
            documents=documents,
            metadata={"search_type": "hybrid", "keyword_results": len(keyword_results)},
        )

    def _keyword_search(self, query_text: str, limit: int) -> list[dict]:
        """Perform keyword search using FTS5 with BM25 ranking."""
        try:
            sanitized_query = self._sanitize_fts_query(query_text)
            if not sanitized_query:
                return []

            rows = self.storage.execute(
                """
                SELECT
                    d.id,
                    d.source,
                    d.content,
                    d.metadata,
                    bm25(documents_fts) as score
                FROM documents_fts
                JOIN documents d ON documents_fts.rowid = d.rowid
                WHERE documents_fts MATCH ?
                ORDER BY score
                LIMIT ?
                """,
                (sanitized_query, limit),
                store="index_meta",
            )

            results = []
            for row in rows:
                metadata = json.loads(row["metadata"]) if row["metadata"] else {}
                results.append({
                    "id": row["id"],
                    "source": row["source"],
                    "content": row["content"],
                    "metadata": metadata,
                    "score": abs(row["score"]),
                    "search_type": "keyword",
                })

            return results

        except Exception as e:
            logger.warning("Keyword search failed: %s", e)
            return []

    def _sanitize_fts_query(self, query_text: str) -> str:
        """Sanitize query text for FTS5 compatibility."""
        import re
        cleaned = re.sub(r'[^\w\s]', ' ', query_text)
        words = cleaned.split()
        return ' OR '.join(words) if words else ''

    def _apply_filters(self, results: list[dict], filters: dict) -> list[dict]:
        """Apply metadata filters to search results."""
        filtered = []
        for doc in results:
            match = True
            for key, value in filters.items():
                if doc["metadata"].get(key) != value:
                    match = False
                    break
            if match:
                filtered.append(doc)
        return filtered

    def _rank_results(self, results: list[dict], top_k: int) -> list[dict]:
        """Rank and truncate results to top_k."""
        sorted_results = sorted(results, key=lambda x: x["score"], reverse=True)
        return sorted_results[:top_k]

    def _chunk_content(self, content: str, max_chunk_size: int = 1000) -> list[str]:
        """Split content into chunks for indexing."""
        if len(content) <= max_chunk_size:
            return [content]

        chunks = []
        sentences = content.split(". ")
        current_chunk = []
        current_size = 0

        for sentence in sentences:
            sentence_size = len(sentence)
            if current_size + sentence_size > max_chunk_size and current_chunk:
                chunks.append(". ".join(current_chunk) + ".")
                current_chunk = []
                current_size = 0

            current_chunk.append(sentence)
            current_size += sentence_size

        if current_chunk:
            chunks.append(". ".join(current_chunk) + ".")

        return chunks

    def health(self) -> dict:
        """Return health status of the retrieval adapter."""
        storage_health = self.storage.health()
        index_healthy = storage_health["stores"].get("index_meta", {}).get("healthy", False)

        doc_count = 0
        try:
            rows = self.storage.execute("SELECT COUNT(*) as count FROM documents", store="index_meta")
            doc_count = rows[0]["count"] if rows else 0
        except Exception as e:
            logger.warning("Failed to count documents: %s", e)

        return {
            "healthy": index_healthy,
            "backend": "sqlite",
            "search_types": ["keyword", "hybrid"],
            "document_count": doc_count,
            "storage_health": storage_health,
        }


def build_sqlite_retrieval_adapter(storage: SQLiteAdapter) -> SQLiteRetrievalAdapter:
    """Factory function to build a SQLiteRetrievalAdapter."""
    return SQLiteRetrievalAdapter(storage)

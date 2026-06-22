from __future__ import annotations

from app.retrieval.contract import RetrievalAdapter, RetrievalQuery, RetrievalResult


class NullRetrievalAdapter(RetrievalAdapter):
    """No-op retrieval backend that preserves the adapter boundary."""

    def query(self, query: RetrievalQuery) -> RetrievalResult:
        return RetrievalResult(
            query=query,
            documents=[],
            metadata={"backend": "none", "wired": False},
        )

    def index(self, documents: list[dict]) -> None:
        if documents:
            raise RuntimeError("Null retrieval adapter cannot index documents.")

    def health(self) -> dict:
        return {
            "component": "retrieval",
            "healthy": True,
            "wired": False,
            "backend": "none",
            "detail": "No retrieval index configured.",
        }

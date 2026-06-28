"""Retrieval endpoint — document indexing and search.

Provides:
- POST /retrieval/index — index documents
- POST /retrieval/search — search indexed documents
- GET /retrieval/stats — retrieval statistics
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/retrieval", tags=["retrieval"])


class DocumentRequest(BaseModel):
    source: str
    content: str
    metadata: dict = Field(default_factory=dict)


class IndexRequest(BaseModel):
    documents: list[DocumentRequest]


class SearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=100)
    metadata_filters: dict = Field(default_factory=dict)


class RetrievedDocument(BaseModel):
    content: str
    source: str
    score: float
    metadata: dict


class SearchResponse(BaseModel):
    documents: list[RetrievedDocument]
    count: int
    metadata: dict


class IndexResponse(BaseModel):
    indexed: int
    chunks: int


@router.post("/index", response_model=IndexResponse)
async def index_documents(request: IndexRequest) -> IndexResponse:
    """Index documents for retrieval."""
    from app.api.main import get_runtime

    runtime = get_runtime()

    docs = [
        {
            "source": doc.source,
            "content": doc.content,
            "metadata": doc.metadata,
        }
        for doc in request.documents
    ]

    runtime.retrieval.index(docs)

    return IndexResponse(indexed=len(docs), chunks=len(docs))


@router.post("/search", response_model=SearchResponse)
async def search_documents(request: SearchRequest) -> SearchResponse:
    """Search indexed documents."""
    from app.api.main import get_runtime
    from app.retrieval.contract import RetrievalQuery

    runtime = get_runtime()

    query = RetrievalQuery(
        query_text=request.query,
        top_k=request.top_k,
        metadata_filters=request.metadata_filters,
    )

    result = runtime.retrieval.query(query)

    return SearchResponse(
        documents=[
            RetrievedDocument(
                content=doc.content,
                source=doc.source,
                score=doc.score,
                metadata=doc.metadata,
            )
            for doc in result.documents
        ],
        count=len(result.documents),
        metadata=result.metadata,
    )


@router.get("/stats")
async def get_retrieval_stats():
    """Get retrieval statistics."""
    from app.api.main import get_runtime

    runtime = get_runtime()

    health = runtime.retrieval.health()

    return {
        "document_count": health["document_count"],
        "search_types": health["search_types"],
        "backend": health["backend"],
        "healthy": health["healthy"],
    }

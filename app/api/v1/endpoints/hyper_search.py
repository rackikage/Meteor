"""Hyper-search API endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.search.orchestrator import HyperSearchOrchestrator


router = APIRouter(prefix="/hyper-search", tags=["hyper-search"])


class HyperSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500,
                       description="Garbled/vague query like 'he ha ha loooo'")
    max_sources: int = Field(default=50, ge=1, le=200)
    depth: int = Field(default=2, ge=1, le=5,
                       description="How deep to search")
    include_content: bool = Field(default=False,
                                  description="Include full content in results")


class HyperSearchResponse(BaseModel):
    query: str
    expanded_forms: list[str]
    winner: str | None
    convergence_score: float
    total_sources_checked: int
    search_time_ms: float
    candidates: list[dict[str, Any]]
    evidence_trail: list[dict[str, Any]]


_orchestrator: HyperSearchOrchestrator | None = None


def init_hyper_search(orchestrator: HyperSearchOrchestrator) -> None:
    global _orchestrator
    _orchestrator = orchestrator


@router.post("/search", response_model=HyperSearchResponse)
async def hyper_search(request: HyperSearchRequest) -> dict[str, Any]:
    if _orchestrator is None:
        raise HTTPException(status_code=503, detail="Hyper-search not initialized")

    result = await _orchestrator.hyper_search(
        raw_query=request.query,
        depth=request.depth,
        max_sources=request.max_sources,
    )

    return HyperSearchResponse(
        query=result.query,
        expanded_forms=[
            result.expanded_query.normalized,
            *result.expanded_query.combinations[:5],
            f"phonetic: {' '.join(result.expanded_query.phonetic_keys[:3])}",
        ],
        winner=result.winner,
        convergence_score=result.convergence_score,
        total_sources_checked=result.total_sources_checked,
        search_time_ms=result.search_time_ms,
        candidates=result.candidates[:10],
        evidence_trail=result.evidence_trail[:5],
    ).model_dump()


@router.get("/expand", response_model=dict[str, Any])
async def expand_query(q: str) -> dict[str, Any]:
    if _orchestrator is None:
        raise HTTPException(status_code=503, detail="Hyper-search not initialized")

    expanded = _orchestrator._expander.expand(q)
    return {
        "original": q,
        "normalized": expanded.normalized,
        "phonetic_keys": expanded.phonetic_keys,
        "combinations": expanded.combinations[:8],
        "ngrams": expanded.ngrams[:8],
        "substrings": expanded.substrings[:15],
    }

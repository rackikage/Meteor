"""Tests for hyper-search orchestrator."""

from __future__ import annotations

import asyncio
import pytest

from app.search.orchestrator import (
    HyperSearchOrchestrator,
    HyperSearchResult,
    SearchSource,
    WebSearchProvider,
)
from app.search.expander import ExpandedQuery


class TestWebSearchProvider:

    def test_mock_search_returns_results(self):
        provider = WebSearchProvider()
        results = asyncio.run(provider.search("test query", max_results=3))
        assert len(results) == 3
        for r in results:
            assert r.url
            assert r.title
            assert r.snippet
            assert r.source_authority > 0

    def test_mock_search_respects_max_results(self):
        provider = WebSearchProvider()
        results = asyncio.run(provider.search("test", max_results=2))
        assert len(results) == 2

    def test_estimate_authority_wikipedia(self):
        assert WebSearchProvider._estimate_authority("https://en.wikipedia.org/wiki/Test") == 1.0

    def test_estimate_authority_fandom(self):
        assert WebSearchProvider._estimate_authority("https://spongebob.fandom.com/wiki/Test") == 1.0

    def test_estimate_authority_unknown(self):
        assert WebSearchProvider._estimate_authority("https://randomsite.com/page") == 0.5

    def test_estimate_authority_edu(self):
        assert WebSearchProvider._estimate_authority("https://cs.stanford.edu/page") == 0.9

    def test_estimate_authority_blog(self):
        assert WebSearchProvider._estimate_authority("https://medium.com/article") == 0.6

    def test_estimate_authority_no_domain(self):
        assert WebSearchProvider._estimate_authority("not a url") == 0.5


class TestHyperSearchOrchestrator:

    def test_hyper_search_basic(self):
        orchestrator = HyperSearchOrchestrator()
        result = asyncio.run(orchestrator.hyper_search("test query"))
        assert isinstance(result, HyperSearchResult)
        assert result.query == "test query"
        assert result.expanded_query is not None
        assert result.search_time_ms > 0

    def test_hyper_search_with_garbled_query(self):
        orchestrator = HyperSearchOrchestrator()
        result = asyncio.run(orchestrator.hyper_search("he ha ha loooo"))
        assert result.query == "he ha ha loooo"
        assert result.expanded_query.normalized == "he ha ha loooo"
        assert len(result.sources["web"]) > 0

    def test_hyper_search_generates_candidates(self):
        orchestrator = HyperSearchOrchestrator()
        result = asyncio.run(orchestrator.hyper_search("Patrick Star SpongeBob"))
        assert isinstance(result.candidates, list)
        assert result.total_sources_checked > 0

    def test_hyper_search_convergence_score(self):
        orchestrator = HyperSearchOrchestrator()
        result = asyncio.run(orchestrator.hyper_search("test"))
        assert 0.0 <= result.convergence_score <= 1.0

    def test_hyper_search_evidence_trail(self):
        orchestrator = HyperSearchOrchestrator()
        result = asyncio.run(orchestrator.hyper_search("test query"))
        assert isinstance(result.evidence_trail, list)

    def test_hyper_search_total_sources(self):
        orchestrator = HyperSearchOrchestrator()
        result = asyncio.run(orchestrator.hyper_search("test"))
        assert result.total_sources_checked >= 0

    def test_score_relevance_exact_match(self):
        orchestrator = HyperSearchOrchestrator()
        expanded = orchestrator._expander.expand("hello world")
        source = SearchSource(
            source_name="web",
            url="https://example.com",
            title="hello world",
            snippet="This is about hello world",
            source_authority=1.0,
        )
        score = orchestrator._score_relevance(source, expanded, "hello world")
        assert score > 50.0

    def test_score_relevance_no_match(self):
        orchestrator = HyperSearchOrchestrator()
        expanded = orchestrator._expander.expand("hello world")
        source = SearchSource(
            source_name="web",
            url="https://example.com",
            title="something else",
            snippet="completely unrelated content",
            source_authority=1.0,
        )
        score = orchestrator._score_relevance(source, expanded, "hello world")
        assert score < 20.0

    def test_score_relevance_authority_bonus(self):
        orchestrator = HyperSearchOrchestrator()
        expanded = orchestrator._expander.expand("test")
        source_high = SearchSource(
            source_name="web",
            url="https://example.com",
            title="test",
            snippet="test content",
            source_authority=1.0,
        )
        source_low = SearchSource(
            source_name="web",
            url="https://example.com",
            title="test",
            snippet="test content",
            source_authority=0.5,
        )
        score_high = orchestrator._score_relevance(source_high, expanded, "test")
        score_low = orchestrator._score_relevance(source_low, expanded, "test")
        assert score_high > score_low

    def test_extract_candidate_names_capitalized(self):
        orchestrator = HyperSearchOrchestrator()
        text = "Patrick Star is a character in SpongeBob"
        names = orchestrator._extract_candidate_names(text)
        assert "Patrick Star" in names

    def test_extract_candidate_names_quoted(self):
        orchestrator = HyperSearchOrchestrator()
        text = 'The character is known as "The Laughing One"'
        names = orchestrator._extract_candidate_names(text)
        assert "The Laughing One" in names

    def test_extract_candidate_names_empty(self):
        orchestrator = HyperSearchOrchestrator()
        names = orchestrator._extract_candidate_names("no names here")
        assert len(names) == 0

    def test_compute_convergence_clear_winner(self):
        candidates = [
            {"confidence": 90.0},
            {"confidence": 20.0},
        ]
        score = HyperSearchOrchestrator._compute_convergence(candidates)
        assert score == 1.0

    def test_compute_convergence_close_match(self):
        candidates = [
            {"confidence": 50.0},
            {"confidence": 45.0},
        ]
        score = HyperSearchOrchestrator._compute_convergence(candidates)
        assert score == 0.25

    def test_compute_convergence_empty(self):
        score = HyperSearchOrchestrator._compute_convergence([])
        assert score == 0.0

    def test_compute_convergence_single_candidate(self):
        candidates = [{"confidence": 80.0}]
        score = HyperSearchOrchestrator._compute_convergence(candidates)
        assert score == 1.0

    def test_detect_candidates_from_sources(self):
        orchestrator = HyperSearchOrchestrator()
        expanded = orchestrator._expander.expand("Patrick Star")
        sources = {
            "web": [
                SearchSource(
                    source_name="wikipedia",
                    url="https://wikipedia.org/Patrick_Star",
                    title="Patrick Star - Wikipedia",
                    snippet="Patrick Star is a character in SpongeBob SquarePants",
                    content="Patrick Star is a fictional character",
                    relevance_score=80.0,
                    source_authority=1.0,
                ),
            ],
        }
        candidates = orchestrator._detect_candidates(sources, expanded, [])
        assert len(candidates) > 0
        assert any("Patrick Star" in c["name"] for c in candidates)

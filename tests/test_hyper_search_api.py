"""Tests for hyper-search API endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.v1.endpoints.hyper_search import init_hyper_search
from app.search.orchestrator import HyperSearchOrchestrator


@pytest.fixture(autouse=True)
def setup_hyper_search():
    orchestrator = HyperSearchOrchestrator()
    init_hyper_search(orchestrator)
    yield


@pytest.fixture
def client():
    return TestClient(app)


class TestHyperSearchEndpoint:

    def test_search_basic(self, client):
        response = client.post("/api/v1/hyper-search/search", json={
            "query": "test query",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "test query"
        assert "winner" in data
        assert "convergence_score" in data
        assert "candidates" in data

    def test_search_with_garbled_query(self, client):
        response = client.post("/api/v1/hyper-search/search", json={
            "query": "he ha ha loooo",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "he ha ha loooo"
        assert len(data["expanded_forms"]) > 0

    def test_search_with_depth(self, client):
        response = client.post("/api/v1/hyper-search/search", json={
            "query": "test",
            "depth": 3,
        })
        assert response.status_code == 200

    def test_search_with_max_sources(self, client):
        response = client.post("/api/v1/hyper-search/search", json={
            "query": "test",
            "max_sources": 10,
        })
        assert response.status_code == 200

    def test_search_empty_query(self, client):
        response = client.post("/api/v1/hyper-search/search", json={
            "query": "",
        })
        assert response.status_code == 422

    def test_search_missing_query(self, client):
        response = client.post("/api/v1/hyper-search/search", json={})
        assert response.status_code == 422

    def test_expand_endpoint(self, client):
        response = client.get("/api/v1/hyper-search/expand?q=hello+world")
        assert response.status_code == 200
        data = response.json()
        assert data["original"] == "hello world"
        assert data["normalized"] == "hello world"
        assert "phonetic_keys" in data
        assert "combinations" in data
        assert "ngrams" in data

    def test_expand_garbled(self, client):
        response = client.get("/api/v1/hyper-search/expand?q=he+ha+ha+loooo")
        assert response.status_code == 200
        data = response.json()
        assert data["original"] == "he ha ha loooo"
        assert len(data["phonetic_keys"]) > 0

    def test_expand_empty_query(self, client):
        response = client.get("/api/v1/hyper-search/expand?q=")
        assert response.status_code == 200
        data = response.json()
        assert data["original"] == ""

    def test_search_response_structure(self, client):
        response = client.post("/api/v1/hyper-search/search", json={
            "query": "test",
        })
        data = response.json()
        assert "query" in data
        assert "expanded_forms" in data
        assert "winner" in data
        assert "convergence_score" in data
        assert "total_sources_checked" in data
        assert "search_time_ms" in data
        assert "candidates" in data
        assert "evidence_trail" in data

    def test_candidates_have_required_fields(self, client):
        response = client.post("/api/v1/hyper-search/search", json={
            "query": "Patrick Star SpongeBob",
        })
        data = response.json()
        if data["candidates"]:
            candidate = data["candidates"][0]
            assert "name" in candidate
            assert "confidence" in candidate
            assert "source_count" in candidate

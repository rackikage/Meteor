"""Multi-source search orchestrator — parallel web, scrape, and local search."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

from app.search.expander import ExpandedQuery, QueryExpander
from app.retrieval.contract import RetrievalQuery

logger = logging.getLogger(__name__)


@dataclass
class SearchSource:
    source_name: str
    url: str
    title: str
    snippet: str
    content: str = ""
    relevance_score: float = 0.0
    source_authority: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class HyperSearchResult:
    query: str
    expanded_query: ExpandedQuery
    sources: dict[str, list[SearchSource]] = field(default_factory=dict)
    candidates: list[dict[str, Any]] = field(default_factory=list)
    convergence_score: float = 0.0
    total_sources_checked: int = 0
    search_time_ms: float = 0.0
    winner: str | None = None
    evidence_trail: list[dict[str, Any]] = field(default_factory=list)


class WebSearchProvider:

    def __init__(self, api_key: str = "", engine_id: str = "") -> None:
        self._api_key = api_key
        self._engine_id = engine_id
        self._use_mock = not api_key

    async def search(self, query: str, max_results: int = 10) -> list[SearchSource]:
        if self._use_mock:
            return self._mock_search(query, max_results)

        import httpx
        params = {
            "key": self._api_key,
            "cx": self._engine_id,
            "q": query,
            "num": min(max_results, 10),
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://www.googleapis.com/customsearch/v1",
                params=params,
            )
            response.raise_for_status()
            data = response.json()

        results = []
        for item in data.get("items", []):
            results.append(SearchSource(
                source_name="google_web",
                url=item.get("link", ""),
                title=item.get("title", ""),
                snippet=item.get("snippet", ""),
                source_authority=self._estimate_authority(item.get("link", "")),
            ))
        return results

    @staticmethod
    def _estimate_authority(url: str) -> float:
        domain = re.search(r"https?://([^/]+)", url)
        if not domain:
            return 0.5
        domain = domain.group(1)

        authoritative = [
            "wikipedia.org", "fandom.com", "imdb.com",
            "britannica.com", "wikia.com", "reddit.com",
            "github.com", "stackoverflow.com", "docs.",
        ]
        for a in authoritative:
            if a in domain:
                return 1.0

        if any(d in domain for d in [".edu", ".gov"]):
            return 0.9

        blogs = ["medium.com", "blog.", "wordpress.com", "substack.com"]
        if any(b in domain for b in blogs):
            return 0.6

        return 0.5

    def _mock_search(self, query: str, max_results: int = 10) -> list[SearchSource]:
        base_domains = [
            ("wikipedia.org", 1.0),
            ("fandom.com", 1.0),
            ("imdb.com", 1.0),
            ("reddit.com", 1.0),
            ("tvguide.com", 0.7),
            ("screenrant.com", 0.7),
        ]

        results = []
        words = query.lower().split()
        for i, (domain, authority) in enumerate(base_domains[:max_results]):
            title_words = query.split()[:3] + [domain.split(".")[0]]
            results.append(SearchSource(
                source_name="web",
                url=f"https://www.{domain}/search?q={query.replace(' ', '+')}",
                title=f"{' '.join(title_words)} - {domain}",
                snippet=f"Results for '{query}' on {domain}. "
                        f"Contains information about {', '.join(words[:3])}.",
                source_authority=authority,
            ))
        return results


class HyperSearchOrchestrator:

    def __init__(
        self,
        retrieval_adapter=None,
        web_provider: WebSearchProvider | None = None,
    ) -> None:
        self._expander = QueryExpander()
        self._retrieval = retrieval_adapter
        self._web = web_provider or WebSearchProvider()

    async def hyper_search(
        self,
        raw_query: str,
        known_corpus: list[str] | None = None,
        depth: int = 2,
        max_sources: int = 50,
    ) -> HyperSearchResult:
        start = time.time()

        expanded = self._expander.expand(raw_query)
        all_searches: list[str] = []

        all_searches.append(expanded.normalized)
        all_searches.extend(expanded.combinations[:3])
        if expanded.phonetic_keys:
            all_searches.append(" ".join(expanded.phonetic_keys[:4]))
        if len(expanded.ngrams) > 1:
            all_searches.extend(expanded.ngrams[-3:])
        all_searches = list(set(all_searches))[:10]

        sources: dict[str, list[SearchSource]] = {
            "web": [],
            "local": [],
        }

        web_tasks = [self._web.search(q, max_results=5) for q in all_searches[:5]]
        web_results = await asyncio.gather(*web_tasks, return_exceptions=True)
        for wr in web_results:
            if isinstance(wr, list):
                sources["web"].extend(wr)

        if self._retrieval:
            for q in all_searches[:3]:
                rq = RetrievalQuery(query_text=q, top_k=3)
                result = self._retrieval.query(rq)
                for doc in result.documents:
                    sources["local"].append(SearchSource(
                        source_name="local_index",
                        url=f"local://{doc.source}",
                        title=doc.source,
                        snippet=doc.content[:200],
                        content=doc.content,
                        source_authority=0.8,
                    ))

        for source_type, results in sources.items():
            for r in results:
                r.relevance_score = self._score_relevance(r, expanded, raw_query)

        candidates = self._detect_candidates(sources, expanded, known_corpus or [])

        convergence = self._compute_convergence(candidates)

        evidence_trail = []
        for c in candidates[:5]:
            evidence_trail.append({
                "candidate": c["name"],
                "confidence": c["confidence"],
                "sources": c["source_count"],
                "top_source": c["top_source"],
                "evidence": c["evidence"][:3],
            })

        elapsed = (time.time() - start) * 1000

        winner = candidates[0]["name"] if candidates else None

        return HyperSearchResult(
            query=raw_query,
            expanded_query=expanded,
            sources=sources,
            candidates=candidates,
            convergence_score=convergence,
            total_sources_checked=sum(len(v) for v in sources.values()),
            search_time_ms=elapsed,
            winner=winner,
            evidence_trail=evidence_trail,
        )

    def _score_relevance(self, result: SearchSource, expanded: ExpandedQuery, raw: str) -> float:
        score = 0.0
        text = f"{result.title} {result.snippet} {result.content}".lower()

        if raw.lower() in text:
            score += 50.0

        if expanded.normalized in text:
            score += 30.0

        words = expanded.normalized.split()
        matched_words = sum(1 for w in words if w in text)
        if words:
            score += (matched_words / len(words)) * 40.0

        for pk in expanded.phonetic_keys[:3]:
            if pk in text:
                score += 15.0

        for sub in expanded.substrings[:10]:
            if len(sub) >= 3 and sub in text:
                score += 5.0

        score *= result.source_authority

        return min(score, 100.0)

    def _detect_candidates(
        self,
        sources: dict[str, list[SearchSource]],
        expanded: ExpandedQuery,
        known_corpus: list[str],
    ) -> list[dict[str, Any]]:
        candidates: dict[str, dict[str, Any]] = {}

        for source_type, results in sources.items():
            for r in results:
                text = f"{r.title} {r.snippet} {r.content}"

                phrases = self._extract_candidate_names(text)

                for phrase in phrases:
                    if phrase not in candidates:
                        candidates[phrase] = {
                            "name": phrase,
                            "confidence": 0.0,
                            "source_count": 0,
                            "sources": set(),
                            "top_source": "",
                            "evidence": [],
                            "relevance_scores": [],
                        }

                    candidates[phrase]["source_count"] += 1
                    candidates[phrase]["sources"].add(r.source_name)
                    candidates[phrase]["evidence"].append({
                        "source": r.source_name,
                        "url": r.url,
                        "snippet": r.snippet[:100],
                    })
                    candidates[phrase]["relevance_scores"].append(r.relevance_score)
                    candidates[phrase]["top_source"] = r.source_name

        for name, data in candidates.items():
            avg_relevance = sum(data["relevance_scores"]) / max(len(data["relevance_scores"]), 1)
            source_diversity = len(data["sources"])
            fuzzy_bonus = 25.0 if self._expander.fuzzy_match(name, expanded.normalized) else 0.0
            data["confidence"] = min(
                (avg_relevance * 0.4) +
                (source_diversity * 15) +
                fuzzy_bonus,
                100.0,
            )

        sorted_candidates = sorted(
            candidates.values(),
            key=lambda x: x["confidence"],
            reverse=True,
        )

        for c in sorted_candidates:
            c["sources"] = list(c["sources"])

        return sorted_candidates[:20]

    def _extract_candidate_names(self, text: str) -> set[str]:
        candidates = set()

        name_patterns = re.findall(r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", text)
        for name in name_patterns:
            if 3 < len(name) < 60:
                candidates.add(name)

        camel_patterns = re.findall(r"([A-Z][a-z]+[A-Z][a-zA-Z]*(?:\s+[A-Z][a-z]+[A-Z]?[a-zA-Z]*)*)", text)
        for name in camel_patterns:
            if 3 < len(name) < 60:
                candidates.add(name)

        quoted = re.findall(r"\"([^\"]+)\"", text)
        for q in quoted:
            if 3 < len(q) < 60:
                candidates.add(q)

        return candidates

    @staticmethod
    def _compute_convergence(candidates: list[dict[str, Any]]) -> float:
        if not candidates:
            return 0.0

        top = candidates[0]["confidence"]
        second = candidates[1]["confidence"] if len(candidates) > 1 else 0

        if top == 0:
            return 0.0

        margin = top - second
        if margin >= 50:
            return 1.0
        elif margin >= 25:
            return 0.75
        elif margin >= 10:
            return 0.5
        else:
            return 0.25

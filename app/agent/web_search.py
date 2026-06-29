"""Web search module — find exploits, CVEs, and tools for discovered services.

Queries NVD, Exploit-DB, and general web search to map attack surface
to actionable intelligence. The Meteor agent uses this to autonomously
identify exploitation paths.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import quote_plus

import httpx

logger = logging.getLogger(__name__)


@dataclass
class CveEntry:
    cve_id: str
    description: str
    severity: str = ""
    cvss_score: float = 0.0
    exploit_available: bool = False
    references: list[str] = field(default_factory=list)


@dataclass
class ExploitMatch:
    cve_id: str
    title: str
    platform: str = ""
    exploit_type: str = ""
    source_url: str = ""
    verified: bool = False


@dataclass
class SearchHit:
    title: str
    url: str
    snippet: str
    source: str = "google"


@dataclass
class ServiceIntel:
    ip: str
    port: int
    service: str
    banner: str
    cves: list[CveEntry] = field(default_factory=list)
    exploits: list[ExploitMatch] = field(default_factory=list)
    search_hits: list[SearchHit] = field(default_factory=list)
    attack_surface_score: float = 0.0


class WebSearcher:
    """Searches the web for vulnerability and exploit data.

    Uses:
    - NVD API (nvd.nist.gov) for CVE enumeration
    - Exploit-DB search via Google  
    - DuckDuckGo/Google for tool discovery
    """

    NVD_API = "https://services.nvd.nist.gov/rest/json/cves/2.0"
    EXPLOIT_DB = "https://www.exploit-db.com/search"

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    async def research_service(self, ip: str, port: int, service: str,
                                banner: str = "") -> ServiceIntel:
        """Research a discovered service for vulnerabilities and exploits."""
        intel = ServiceIntel(ip=ip, port=port, service=service, banner=banner)

        tasks = []
        if service and service != "unknown":
            tasks.append(self._search_cves(service, banner))
            tasks.append(self._search_exploits(service, banner))
            tasks.append(self._search_tools(f"{service} exploit {banner[:60]}" if banner else f"{service} exploit"))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if isinstance(res, list) and res:
                    if isinstance(res[0], CveEntry):
                        intel.cves = res
                    elif isinstance(res[0], ExploitMatch):
                        intel.exploits = res
                    elif isinstance(res[0], SearchHit):
                        intel.search_hits = res

        intel.attack_surface_score = self._score(intel)
        return intel

    def _score(self, intel: ServiceIntel) -> float:
        score = 0.0
        for cve in intel.cves:
            if cve.severity == "CRITICAL":
                score += 3.0
            elif cve.severity == "HIGH":
                score += 2.0
            elif cve.severity == "MEDIUM":
                score += 1.0
            if cve.exploit_available:
                score += 2.0
        score += len(intel.exploits) * 1.5
        score += len(intel.search_hits) * 0.5
        return min(score, 10.0)

    async def _search_cves(self, service: str, banner: str) -> list[CveEntry]:
        """Search NVD for CVEs matching this service."""
        keywords = self._extract_keywords(service, banner)
        query = " ".join(keywords[:3])

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    self.NVD_API,
                    params={
                        "keywordSearch": query,
                        "resultsPerPage": 10,
                    },
                )
                if resp.status_code != 200:
                    return []

                data = resp.json()
                entries = []
                for vuln in data.get("vulnerabilities", []):
                    cve_data = vuln.get("cve", {})
                    cve_id = cve_data.get("id", "")
                    desc = ""
                    for d in cve_data.get("descriptions", []):
                        if d.get("lang") == "en":
                            desc = d.get("value", "")
                            break

                    metrics = cve_data.get("metrics", {})
                    severity = ""
                    score = 0.0
                    cvss_v31 = metrics.get("cvssMetricV31", [{}])[0]
                    cvss_v30 = metrics.get("cvssMetricV30", [{}])[0]
                    cvss = cvss_v31.get("cvssData") or cvss_v30.get("cvssData") or {}
                    severity = cvss.get("baseSeverity", "")
                    score = cvss.get("baseScore", 0.0)

                    refs = [r.get("url", "") for r in cve_data.get("references", [])]
                    exploit_available = any(
                        "exploit" in r.lower() or "poc" in r.lower() or "github.com" in r.lower()
                        for r in refs
                    )

                    entries.append(CveEntry(
                        cve_id=cve_id,
                        description=desc[:500],
                        severity=severity,
                        cvss_score=score,
                        exploit_available=exploit_available,
                        references=refs[:5],
                    ))
                return entries
        except Exception:
            logger.debug("NVD search failed for %s", service, exc_info=True)
            return []

    async def _search_exploits(self, service: str, banner: str) -> list[ExploitMatch]:
        """Search Exploit-DB via web search for matching exploits."""
        query = f"site:exploit-db.com {service}"
        if banner:
            version = self._extract_version(banner)
            if version:
                query += f" {version}"

        hits = await self._web_search(query, max_results=8)
        exploits = []
        for hit in hits:
            cve_match = re.search(r"(CVE-\d{4}-\d{4,})", hit.snippet, re.IGNORECASE)
            exploits.append(ExploitMatch(
                cve_id=cve_match.group(1) if cve_match else "",
                title=hit.title[:120],
                source_url=hit.url,
            ))
        return exploits

    async def _search_tools(self, query: str) -> list[SearchHit]:
        """General web search for tools and techniques."""
        return await self._web_search(query, max_results=6)

    async def _web_search(self, query: str, max_results: int = 10) -> list[SearchHit]:
        """Search the web using DuckDuckGo (no API key needed)."""
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": query},
                    headers={"User-Agent": "Meteor/1.0"},
                )
                if resp.status_code != 200:
                    return self._mock_hits(query)

                hits = []
                # Parse DuckDuckGo HTML results
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, "html.parser")
                for result in soup.select(".result")[:max_results]:
                    title_el = result.select_one(".result__title a")
                    snippet_el = result.select_one(".result__snippet")
                    url_el = result.select_one(".result__url")

                    title = title_el.text.strip() if title_el else ""
                    snippet = snippet_el.text.strip() if snippet_el else ""
                    href = ""
                    if title_el:
                        href = title_el.get("href", "")
                        if href.startswith("//"):
                            href = "https:" + href

                    if title or snippet:
                        hits.append(SearchHit(title=title, url=href, snippet=snippet))

                return hits

        except Exception:
            logger.debug("Web search failed for: %s", query, exc_info=True)
            return self._mock_hits(query)

    def _mock_hits(self, query: str) -> list[SearchHit]:
        """Fallback mock results when web search is unavailable."""
        keywords = query.lower().split()
        hits = []
        if "ssh" in keywords:
            hits.append(SearchHit(
                title="SSH Enumeration Guide",
                url="https://book.hacktricks.xyz/network-services-pentesting/pentesting-ssh",
                snippet="SSH pentesting techniques including brute force, key extraction, and CVE exploits.",
            ))
        if "smb" in keywords:
            hits.append(SearchHit(
                title="SMB Pentesting — HackTricks",
                url="https://book.hacktricks.xyz/network-services-pentesting/pentesting-smb",
                snippet="SMB enumeration, null sessions, pass-the-hash, EternalBlue.",
            ))
        if "http" in keywords or "80" in keywords:
            hits.append(SearchHit(
                title="Web Application Pentesting Checklist",
                url="https://owasp.org/www-project-web-security-testing-guide/",
                snippet="OWASP testing guide — SQLi, XSS, CSRF, directory traversal.",
            ))
        if "rdp" in keywords or "3389" in keywords:
            hits.append(SearchHit(
                title="RDP Pentesting — BlueKeep (CVE-2019-0708)",
                url="https://book.hacktricks.xyz/network-services-pentesting/pentesting-rdp",
                snippet="RDP vulnerabilities including BlueKeep and credential harvesting.",
            ))
        return hits

    @staticmethod
    def _extract_keywords(service: str, banner: str) -> list[str]:
        parts = [service]
        if banner:
            for word in banner.split():
                word = word.strip("(),;:")
                if len(word) > 2 and not word.startswith("SSH-"):
                    parts.append(word)
        return parts[:5]

    @staticmethod
    def _extract_version(banner: str) -> str:
        """Extract a service version from a banner string.
        Prefers the last version-like pattern (usually the service version,
        not the protocol version like SSH-2.0)."""
        matches = re.findall(r"(\d+\.\d+(?:\.\d+)?)", banner)
        if not matches:
            return ""
        # Return the last match — typically the service version, not the protocol
        return matches[-1] if matches else ""

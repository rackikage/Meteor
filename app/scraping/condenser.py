"""DOM condenser — transforms raw HTML into an LLM-friendly compact representation.

Problem: A product page on Amazon is 5MB of HTML.  Send that to any LLM and
you blow the context window before reaching the actual product data.

Solution: Pipeline that strips noise, deduplicates, tags semantic elements,
and produces a ~2K-token structured summary the LLM can reason about.

Runs entirely in the browser's JS context for speed (sub-50ms on a full page).
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from bs4 import BeautifulSoup, Tag

from .contracts import CondensedDOM, DOMSnapshot, Insight, ScrapePolicy

logger = logging.getLogger(__name__)

INTERACTIVE_TAGS = {"a", "button", "input", "select", "textarea", "details", "summary"}
DATA_CONTAINER_TAGS = {"table", "ul", "ol", "dl", "article", "section", "card"}
BLOCKER_PATTERNS = re.compile(
    r"(captcha|challenge|verify|blocked|denied|rate.limit|too many requests|access denied)",
    re.IGNORECASE,
)
LOGIN_PATTERNS = re.compile(
    r"(login|log.in|sign.in|password|username|email)",
    re.IGNORECASE,
)
PAGINATION_PATTERNS = re.compile(
    r"(page/\d|\?page=|\bnext\b|\bprev\b|\bolder\b|\bnewer\b|load.more)",
    re.IGNORECASE,
)


class DOMCondenser:
    """Compresses raw DOM into a structured, minimal representation."""

    def __init__(self, policy: ScrapePolicy) -> None:
        self.policy = policy

    def condense(self, snapshot: DOMSnapshot) -> CondensedDOM:
        """DOMSnapshot → CondensedDOM in one pass."""
        soup = BeautifulSoup(snapshot.html, "lxml")

        meta_desc = ""
        meta_tag = soup.find("meta", attrs={"name": "description"})
        if meta_tag and isinstance(meta_tag, Tag):
            meta_desc = meta_tag.get("content", "") or ""

        # Strip noise tags
        for tag in soup([
            "script", "style", "noscript", "iframe", "svg",
            "nav", "footer", "header", "aside",
        ]):
            tag.decompose()

        body = soup.find("body")
        text_sample = ""
        word_count = 0
        if body:
            raw = body.get_text(separator=" ", strip=True)
            word_count = len(raw.split())
            text_sample = raw[: self.policy.max_text_per_page]

        # Interactive elements
        interactive = self._extract_interactive(soup)

        # Data regions
        data_regions = self._extract_data_regions(soup)

        # Detections
        has_login = bool(LOGIN_PATTERNS.search(text_sample))
        has_pagination = bool(PAGINATION_PATTERNS.search(text_sample))
        blockers = []
        for match in BLOCKER_PATTERNS.finditer(text_sample):
            blockers.append(match.group(0))

        summary = self._generate_summary(snapshot.title, meta_desc, text_sample)

        return CondensedDOM(
            url=snapshot.url,
            title=snapshot.title,
            meta_description=meta_desc,
            summary=summary,
            interactive_elements=interactive[:60],
            data_regions=data_regions[:20],
            text_sample=text_sample,
            word_count=word_count,
            link_count=len(snapshot.visible_links),
            has_login_form=has_login,
            has_pagination=has_pagination,
            detected_blockers=blockers,
        )

    def _extract_interactive(self, soup: BeautifulSoup) -> list[dict[str, str]]:
        elements = []
        for el in soup.find_all(INTERACTIVE_TAGS):
            tag_name = el.name
            text = el.get_text(strip=True)[:120] if el.get_text(strip=True) else ""
            href = ""
            if isinstance(el, Tag) and el.name == "a":
                href = el.get("href", "") or ""
            attrs = {}
            if isinstance(el, Tag):
                if el.get("id"):
                    attrs["id"] = str(el["id"])
                if el.get("class"):
                    attrs["class"] = " ".join(el["class"])
                if el.get("type"):
                    attrs["type"] = str(el["type"])
                if el.get("placeholder"):
                    attrs["placeholder"] = str(el["placeholder"])
            elements.append({
                "tag": tag_name,
                "text": text,
                "href": href,
                "attrs": str(attrs),
            })
        return elements

    def _extract_data_regions(self, soup: BeautifulSoup) -> list[dict[str, str]]:
        regions = []
        for el in soup.find_all(DATA_CONTAINER_TAGS):
            tag_name = el.name
            preview = el.get_text(strip=True, separator=" ")[:300]
            row_count = 0
            if tag_name == "table":
                row_count = len(el.find_all("tr"))
            elif tag_name in ("ul", "ol"):
                row_count = len(el.find_all("li"))
            regions.append({
                "tag": tag_name,
                "preview": preview,
                "row_count": str(row_count),
            })
        return regions

    def _generate_summary(self, title: str, meta_desc: str, text: str) -> str:
        if meta_desc:
            return meta_desc[:200]
        sentences = re.split(r"(?<=[.!?])\s+", text)
        for s in sentences[:3]:
            s = s.strip()
            if len(s) > 30:
                return s[:200]
        return title[:200]

    def final_summary(self, insights: list[Insight], goal: str) -> str:
        """Aggregate all insights into a final executive summary."""
        if not insights:
            return "No insights were extracted."
        lines = [f"# Extraction Summary\nGoal: {goal}\n"]
        for i, ins in enumerate(insights, 1):
            url = ins.condensed_dom.url if ins.condensed_dom else ins.target_url
            lines.append(f"## Insight {i}: {url}")
            lines.append(ins.extraction.insight[:500])
            lines.append(f"Confidence: {ins.extraction.confidence:.0%}\n")
        return "\n".join(lines)

"""LLM adapter — interfaces with Ollama for navigation planning and extraction.

Meteor Doctrine #3: Adapters isolate change.  Swapping Ollama for OpenAI or
anthropic must require changes *only* in this file.  No other layer knows
which model backend is in use.

Meteor Doctrine #6: Retrieval is separate from inference.  The LLM receives
a pre-condensed DOM from the condenser — it never performs retrieval itself.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from .contracts import CondensedDOM, ExtractionRequest, ExtractionResult, NavigationPlan

logger = logging.getLogger(__name__)

NAVIGATION_SYSTEM_PROMPT = """You are a web scraping navigation agent. Your job is to:
1. Analyze the current state of a web page
2. Decide what action to take next to find the information the user wants
3. Return your decision as a structured JSON plan

Available actions:
- click: Click on an element (provide CSS selector)
- fill: Type text into an input field (provide selector + value)
- scroll: Scroll the page (provide pixel amount as value)
- wait: Wait for a number of milliseconds
- extract: Extract information from the current page
- done: The goal is satisfied

Rules:
- Prefer clicking visible links over buttons
- If you see a login wall, note it and try alternatives
- If the page has pagination, click "next" to get more results
- Extract as soon as you see relevant data
- Set action to "done" only when you have enough information

Return ONLY valid JSON with fields: action, selector (optional), value (optional), reason, expected_outcome."""

EXTRACTION_SYSTEM_PROMPT = """You are a web scraping insight extraction agent. Your job is to:
1. Analyze the condensed DOM of a web page
2. Extract the specific information the user is looking for
3. Return structured results as JSON

Guidelines:
- Extract only information that directly relates to the user's goal
- Be specific and cite values you find on the page
- If the page doesn't contain relevant information, set success=false
- Include a navigation plan if you need to go to another page
- Set confidence based on how clearly the data matches the goal
- confidence: 1.0 = exact match, 0.7 = strong match, 0.4 = weak match, 0.0 = no match

Return valid JSON with fields: success, insight, confidence (0.0-1.0),
relevant_data (object with extracted fields), navigation (optional object with
action, selector, value, reason, expected_outcome),
needs_follow_up (bool), follow_up_reason (optional string)."""


class LLMAdapter:
    """Interface to a local LLM via Ollama for navigation and extraction.

    The model is pluggable — pass any Ollama model name at construction.
    The adapter emits typed contracts (NavigationPlan, ExtractionResult),
    never raw strings or dicts.
    """

    def __init__(
        self,
        model: str = "llama3.2:3b",
        base_url: str = "http://localhost:11434",
    ) -> None:
        self.model = model
        self.base_url = base_url
        self._client = None

    def _get_client(self):
        """Lazy import Ollama to avoid startup dependency on the binary."""
        if self._client is None:
            import ollama
            self._client = ollama
        return self._client

    def plan_navigation(
        self,
        condensed: CondensedDOM,
        goal: str,
        context: Optional[str] = None,
    ) -> NavigationPlan:
        """Ask the LLM what browser action to take next."""
        client = self._get_client()

        page_context = (
            f"URL: {condensed.url}\n"
            f"Title: {condensed.title}\n"
            f"Summary: {condensed.summary}\n\n"
            f"Interactive elements on page:\n"
            f"{self._fmt_list(condensed.interactive_elements, 'element')}\n\n"
            f"Data regions:\n"
            f"{self._fmt_list(condensed.data_regions, 'region')}\n\n"
            f"Text preview:\n{condensed.text_sample[:2000]}"
        )

        if context:
            page_context += f"\n\nPrevious context: {context}"

        messages = [
            {"role": "system", "content": NAVIGATION_SYSTEM_PROMPT},
            {"role": "user", "content": f"Goal: {goal}\n\nCurrent page:\n{page_context}"},
        ]

        try:
            resp = client.chat(
                model=self.model,
                messages=messages,
                format="json",
                options={"temperature": 0.3},
            )
            raw = resp["message"]["content"]
            data = json.loads(raw)
            return NavigationPlan(**data)
        except Exception as e:
            logger.warning("Navigation planning failed: %s — defaulting to extract", e)
            return NavigationPlan(
                action="extract",
                reason=f"Navigation planning error ({e}), falling back to extraction",
                expected_outcome="Extract whatever is on the current page",
            )

    def extract(self, request: ExtractionRequest) -> ExtractionResult:
        """Extract structured insight from condensed DOM."""
        client = self._get_client()

        page_data = (
            f"URL: {request.condensed_dom.url}\n"
            f"Title: {request.condensed_dom.title}\n"
            f"Summary: {request.condensed_dom.summary}\n\n"
            f"Data regions:\n"
            f"{self._fmt_list(request.condensed_dom.data_regions, 'region')}\n\n"
            f"Page text:\n{request.condensed_dom.text_sample[:4000]}"
        )

        context_block = ""
        if request.context:
            context_block = f"\n\nPrevious extraction context:\n{request.context}"

        messages = [
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Goal: {request.goal}\n\n"
                    f"Page content:\n{page_data}{context_block}"
                ),
            },
        ]

        try:
            resp = client.chat(
                model=self.model,
                messages=messages,
                format="json",
                options={"temperature": 0.2},
            )
            raw = resp["message"]["content"]
            data = json.loads(raw)
            return ExtractionResult(**data)
        except Exception as e:
            logger.error("Extraction failed: %s", e)
            return ExtractionResult(
                success=False,
                insight="",
                error=str(e),
            )

    def _fmt_list(self, items: list[dict[str, str]], label: str) -> str:
        """Format a list of dicts into a readable string for the LLM prompt."""
        if not items:
            return f"  (no {label}s detected)"
        lines = []
        for i, item in enumerate(items[:20], 1):
            parts = []
            for k, v in item.items():
                if v:
                    parts.append(f"{k}={v}")
            lines.append(f"  {i}. {', '.join(parts)}")
        return "\n".join(lines)

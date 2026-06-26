"""Meteor Scraping — LLM-driven agentic insight extraction.

Layers:
  contracts      — typed Pydantic models for all data flowing through the pipeline
  browser_adapter — Playwright-based browser automation with anti-detection
  condenser      — DOM condensation: raw HTML → LLM-friendly compact representation
  llm_adapter    — Ollama model interface for navigation planning and extraction
  orchestrator   — insight loop state machine: navigate → condense → extract → act → repeat
  policy         — policy rules constraining scraper behaviour (domains, rate, depth)
  storage        — evidence persistence to JSON artifacts on disk
  cli            — CLI entry point: meteor-scrape, meteor-scrape list, meteor-scrape view
"""

from .contracts import (
    CondensedDOM,
    DOMSnapshot,
    Evidence,
    ExtractionRequest,
    ExtractionResult,
    Insight,
    NavigationPlan,
    ScrapePolicy,
    ScrapeStatus,
    ScrapeTarget,
    SessionState,
)
from .orchestrator import ScrapingOrchestrator

__all__ = [
    "CondensedDOM",
    "DOMSnapshot",
    "Evidence",
    "ExtractionRequest",
    "ExtractionResult",
    "Insight",
    "NavigationPlan",
    "ScrapePolicy",
    "ScrapeStatus",
    "ScrapeTarget",
    "ScrapingOrchestrator",
    "SessionState",
]

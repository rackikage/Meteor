"""Meteor Scraper — typed contracts for the insight extraction pipeline.

Every contract here is a Pydantic model. This gives us runtime validation,
JSON serialisation, and field-level documentation without extra boilerplate.

These are NOT dataclasses — they are versioned, validated contracts that
outlive implementations (Doctrine #8). The choice of Pydantic over dataclasses
is intentional: scraping needs schema enforcement across session boundaries
and across async boundaries where a TypedDict would silently pass garbage.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class ScrapeStatus(str, Enum):
    PENDING = "pending"
    NAVIGATING = "navigating"
    CONDENSING = "condensing"
    EXTRACTING = "extracting"
    COMPLETE = "complete"
    FAILED = "failed"
    BLOCKED = "blocked"


class ScrapeTarget(BaseModel):
    """A structured target describing *what* to scrape and *why*."""

    url: str = Field(..., description="Target URL to begin navigation from")
    goal: str = Field(..., description="High-level extraction goal in natural language")
    max_depth: int = Field(default=3, ge=1, le=10)
    max_pages: int = Field(default=10, ge=1, le=100)
    proxy: Optional[str] = Field(default=None)
    user_agent: Optional[str] = Field(default=None)
    cookies: Dict[str, str] = Field(default_factory=dict)
    headers: Dict[str, str] = Field(default_factory=dict)
    viewport: tuple[int, int] = Field(default=(1920, 1080))

    @field_validator("url")
    @classmethod
    def _must_be_http(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError(f"URL must start with http:// or https://: {v}")
        return v


class NavigationPlan(BaseModel):
    """The LLM's plan for what browser action to take next."""

    action: str = Field(..., description="click | fill | scroll | wait | extract | done")
    selector: Optional[str] = Field(default=None, description="CSS/XPath selector")
    value: Optional[str] = Field(default=None, description="Value for fill or scroll (px)")
    reason: str = Field(..., description="Why this action, in natural language")
    expected_outcome: str = Field(..., description="What should happen after")


class DOMSnapshot(BaseModel):
    """Raw DOM state captured at a moment in time."""

    url: str
    title: str
    html: str = Field(..., description="Full outer HTML")
    text_content: str = Field(..., description="All visible text, stripped")
    visible_links: list[dict[str, str]] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    viewport_size: tuple[int, int] = Field(default=(0, 0))
    scroll_position: tuple[int, int] = Field(default=(0, 0))


class CondensedDOM(BaseModel):
    """Heavily compressed DOM representation for LLM consumption."""

    url: str
    title: str
    meta_description: str = ""
    summary: str = Field(..., description="1-3 sentence summary of page purpose")
    interactive_elements: list[dict[str, str]] = Field(
        default_factory=list,
        description="Buttons, links, forms, inputs — actionable items",
    )
    data_regions: list[dict[str, str]] = Field(
        default_factory=list,
        description="Tables, lists, cards — structured data areas",
    )
    text_sample: str = Field(..., description="First ~2000 chars of meaningful body text")
    word_count: int = 0
    link_count: int = 0
    has_login_form: bool = False
    has_pagination: bool = False
    detected_blockers: list[str] = Field(default_factory=list)


class ExtractionRequest(BaseModel):
    """Prompt for the LLM to extract structured insight from condensed DOM."""

    goal: str
    condensed_dom: CondensedDOM
    context: Optional[str] = Field(default=None, description="Previous extraction memory")
    format_hint: Optional[str] = Field(default=None)


class ExtractionResult(BaseModel):
    """Structured output from the LLM after analysing a page."""

    success: bool
    insight: str = Field(..., description="The extracted insight in natural language")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    relevant_data: dict[str, Any] = Field(default_factory=dict)
    navigation: Optional[NavigationPlan] = Field(default=None)
    needs_follow_up: bool = False
    follow_up_reason: Optional[str] = None
    error: Optional[str] = None


class Insight(BaseModel):
    """A complete, persisted insight artifact — the core evidence unit."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    session_id: str
    target_url: str
    goal: str
    extraction: ExtractionResult
    condensed_dom: CondensedDOM
    raw_snapshot: Optional[str] = Field(default=None, description="First 8KB of raw HTML for audit")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tags: list[str] = Field(default_factory=list)


class Evidence(BaseModel):
    """Container for all evidence collected in a session."""

    session_id: str
    target: ScrapeTarget
    insights: list[Insight] = Field(default_factory=list)
    navigation_log: list[NavigationPlan] = Field(default_factory=list)
    status: ScrapeStatus = ScrapeStatus.PENDING
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = Field(default=None)
    pages_visited: int = 0
    errors: list[str] = Field(default_factory=list)


class SessionState(BaseModel):
    """Mutable runtime state for a scraping session."""

    target: ScrapeTarget
    evidence: Evidence
    current_url: Optional[str] = None
    current_depth: int = 0
    pages_seen: set[str] = Field(default_factory=set)
    cross_session_memory: dict[str, Any] = Field(default_factory=dict)

    model_config = {"arbitrary_types_allowed": True}


class ScrapePolicy(BaseModel):
    """Policy configuration constraining scraper behaviour."""

    max_concurrent_sessions: int = Field(default=3, ge=1, le=20)
    request_delay_ms: int = Field(default=1500, ge=200, le=30000)
    max_retries: int = Field(default=3, ge=0, le=10)
    respect_robots_txt: bool = True
    respect_rate_limits: bool = True
    block_known_bot_traps: bool = True
    max_page_size_bytes: int = Field(default=5_000_000)
    screenshot_on_error: bool = True
    headless: bool = True
    stealth_mode: bool = True
    allowed_domains: list[str] = Field(default_factory=list)
    blocked_domains: list[str] = Field(default_factory=list)
    block_captcha: bool = True
    max_text_per_page: int = Field(default=15_000, description="Max chars fed to LLM per page")

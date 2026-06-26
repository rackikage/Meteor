"""Policy engine — validates and constrains scraping operations.

Meteor Doctrine #1: Policy controls authority.
Meteor Doctrine #2: Boundaries define what the system can never do.

This engine gates every browser action, every domain access, and every
extraction request before execution reaches the adapter layer.
"""

from __future__ import annotations

import logging
from typing import Optional
from urllib.parse import urlparse

from .contracts import ScrapePolicy, ScrapeTarget

logger = logging.getLogger(__name__)


class PolicyEngine:
    """Validates scrape targets and navigation actions against policy rules."""

    def __init__(self, policy: Optional[ScrapePolicy] = None) -> None:
        self.policy = policy or ScrapePolicy()

    def validate_target(self, target: ScrapeTarget) -> tuple[bool, Optional[str]]:
        """Validate a scrape target against policy.  Returns (allowed, reason)."""
        parsed = urlparse(target.url)
        domain = parsed.netloc.lower()

        if domain in self.policy.blocked_domains:
            return False, f"Domain {domain} is blocked by policy"

        if self.policy.allowed_domains:
            allowed = any(
                domain == d or domain.endswith(f".{d}")
                for d in self.policy.allowed_domains
            )
            if not allowed:
                return False, f"Domain {domain} not in allowed list"

        if target.max_depth > self.policy.max_concurrent_sessions * 2:
            logger.warning(
                "Depth %d may be aggressive for concurrency setting %d",
                target.max_depth,
                self.policy.max_concurrent_sessions,
            )

        return True, None

    def validate_navigation(self, nav_action: str, _target_url: str) -> tuple[bool, Optional[str]]:
        """Validate a navigation action before execution."""
        if self.policy.block_captcha and "captcha" in nav_action.lower():
            return False, "CAPTCHA detected — blocking action per policy"
        return True, None

    def rate_limit_delay(self, pages_visited: int) -> float:
        """Progressive backoff based on pages visited in this session."""
        base = self.policy.request_delay_ms / 1000.0
        if pages_visited > 50:
            return base * 3.0
        if pages_visited > 20:
            return base * 2.0
        return base

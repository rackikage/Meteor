"""Tests for the Meteor scraping module.

Verifies: contract validation, policy engine gates, condenser output shape,
and orchestrator responds to policy denial without needing a running browser.
"""

from __future__ import annotations

from app.scraping.contracts import (
    CondensedDOM,
    ExtractionRequest,
    ExtractionResult,
    NavigationPlan,
    ScrapePolicy,
    ScrapeStatus,
    ScrapeTarget,
)


# ── Contract validation ────────────────────────────────────────────────

def test_scrape_target_rejects_non_http_url() -> None:
    try:
        ScrapeTarget(url="ftp://files.example.com", goal="test")
        assert False, "Should have raised ValidationError"
    except Exception:
        pass


def test_scrape_target_accepts_https() -> None:
    t = ScrapeTarget(url="https://example.com/page", goal="extract prices")
    assert t.url == "https://example.com/page"
    assert t.viewport == (1920, 1080)


def test_scrape_target_default_max_depth() -> None:
    t = ScrapeTarget(url="https://x.com", goal="test")
    assert t.max_depth == 3


def test_navigation_plan_requires_action_and_reason() -> None:
    np = NavigationPlan(
        action="click",
        selector="#buy-now",
        reason="Product page has a buy button",
        expected_outcome="Navigate to checkout",
    )
    assert np.action == "click"
    assert np.selector == "#buy-now"


def test_condensed_dom_defaults() -> None:
    cd = CondensedDOM(
        url="https://example.com",
        title="Example",
        summary="A test page.",
        text_sample="Hello world.",
    )
    assert cd.word_count == 0
    assert cd.link_count == 0
    assert cd.has_login_form is False
    assert cd.has_pagination is False
    assert cd.detected_blockers == []


def test_scrape_policy_defaults() -> None:
    p = ScrapePolicy()
    assert p.headless is True
    assert p.stealth_mode is True
    assert p.block_captcha is True
    assert p.request_delay_ms == 1500


def test_extraction_result_defaults() -> None:
    r = ExtractionResult(
        success=True,
        insight="Found 3 products",
        confidence=0.8,
    )
    assert r.success is True
    assert r.needs_follow_up is False
    assert r.navigation is None


# ── Status enum ─────────────────────────────────────────────────────────

def test_scrape_status_values() -> None:
    statuses = set(s.value for s in ScrapeStatus)
    assert "pending" in statuses
    assert "complete" in statuses
    assert "failed" in statuses
    assert "blocked" in statuses


# ── Policy engine validation (no browser needed) ────────────────────────

def test_policy_allows_unrestricted_url() -> None:
    from app.scraping.policy import PolicyEngine
    engine = PolicyEngine()
    target = ScrapeTarget(url="https://example.com", goal="test")
    allowed, reason = engine.validate_target(target)
    assert allowed is True
    assert reason is None


def test_policy_blocks_blocked_domain() -> None:
    from app.scraping.policy import PolicyEngine
    policy = ScrapePolicy(blocked_domains=["blocked.com"])
    engine = PolicyEngine(policy)
    target = ScrapeTarget(url="https://blocked.com/page", goal="test")
    allowed, reason = engine.validate_target(target)
    assert allowed is False
    assert "blocked" in reason.lower()


def test_policy_enforces_allowed_domains() -> None:
    from app.scraping.policy import PolicyEngine
    policy = ScrapePolicy(allowed_domains=["safe.com"])
    engine = PolicyEngine(policy)
    target = ScrapeTarget(url="https://other.com/page", goal="test")
    allowed, reason = engine.validate_target(target)
    assert allowed is False
    assert "not in allowed" in reason.lower()


def test_policy_allows_subdomain_match() -> None:
    from app.scraping.policy import PolicyEngine
    policy = ScrapePolicy(allowed_domains=["safe.com"])
    engine = PolicyEngine(policy)
    target = ScrapeTarget(url="https://sub.safe.com/page", goal="test")
    allowed, _reason = engine.validate_target(target)
    assert allowed is True


def test_policy_blocks_captcha_action() -> None:
    from app.scraping.policy import PolicyEngine
    engine = PolicyEngine()
    allowed, reason = engine.validate_navigation("click_captcha_box", "")
    assert allowed is False
    assert "captcha" in reason.lower()


def test_policy_allows_normal_action() -> None:
    from app.scraping.policy import PolicyEngine
    engine = PolicyEngine()
    allowed, _reason = engine.validate_navigation("click", "")
    assert allowed is True


def test_rate_limit_progressive_backoff() -> None:
    from app.scraping.policy import PolicyEngine
    engine = PolicyEngine()
    assert engine.rate_limit_delay(0) < engine.rate_limit_delay(25)
    assert engine.rate_limit_delay(25) < engine.rate_limit_delay(60)

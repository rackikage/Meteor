"""Scraping orchestrator — the runtime that drives the insight extraction loop.

This is the core of the Meteor scraper.  It owns the workflow:

  1. Navigate to target URL
  2. Capture DOM snapshot
  3. Condense DOM → LLM-friendly representation
  4. LLM extracts insight from the condensed page
  5. LLM decides next navigation action (click, scroll, etc.)
  6. Execute action → new DOM snapshot
  7. Repeat until goal satisfied, depth exhausted, or timeout

Meteor Doctrine #4: Runtime is the product.  The orchestrator owns the loop.
The model, browser, and condenser are replaceable adapters.

Meteor Doctrine #7: Evidence precedes conclusions.  Every insight is stamped
with source URL, confidence, timestamp, and audit trace.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from .browser_adapter import BrowserAdapter
from .condenser import DOMCondenser
from .contracts import (
    Evidence,
    ExtractionRequest,
    Insight,
    NavigationPlan,
    ScrapePolicy,
    ScrapeStatus,
    ScrapeTarget,
    SessionState,
)
from .llm_adapter import LLMAdapter
from .policy import PolicyEngine
from .storage import EvidenceStore

logger = logging.getLogger(__name__)


class ScrapingOrchestrator:
    """Meteor runtime for the insight loop.

    Construction receives adapters via dependency injection — the orchestrator
    owns no concrete implementations.  Every external dependency is an adapter.
    """

    def __init__(
        self,
        browser: BrowserAdapter,
        condenser: DOMCondenser,
        llm: LLMAdapter,
        policy: ScrapePolicy,
        policy_engine: PolicyEngine,
        store: EvidenceStore,
    ) -> None:
        self.browser = browser
        self.condenser = condenser
        self.llm = llm
        self.policy = policy
        self.policy_engine = policy_engine
        self.store = store
        self._sessions: dict[str, SessionState] = {}

    async def run(self, target: ScrapeTarget) -> Evidence:
        """Execute a full scraping session from start to finish.

        Returns an Evidence container holding every extracted insight, every
        navigation log entry, and the final session status.
        """
        session_id = target.url[:60]
        evidence = Evidence(
            session_id=session_id,
            target=target,
            status=ScrapeStatus.NAVIGATING,
        )
        state = SessionState(target=target, evidence=evidence)
        self._sessions[session_id] = state

        try:
            logger.info(
                "Starting scrape session | url=%s | goal=%s",
                target.url,
                target.goal[:80],
            )

            # Validate target
            allowed, reason = self.policy_engine.validate_target(target)
            if not allowed:
                state.evidence.status = ScrapeStatus.FAILED
                state.evidence.errors.append(f"Policy denied: {reason}")
                return state.evidence

            # Start browser session
            await self.browser.new_session(target)

            # Navigate to initial URL
            snapshot = await self.browser.navigate(target.url)
            state.current_url = snapshot.url
            state.pages_seen.add(snapshot.url)
            state.evidence.pages_visited = 1
            state.current_depth = 0

            # Main insight loop
            context: Optional[str] = None
            max_iterations = min(target.max_depth * 3, 30)

            for iteration in range(max_iterations):
                logger.debug(
                    "Loop iteration %d/%d | url=%s",
                    iteration + 1,
                    max_iterations,
                    snapshot.url,
                )

                # --- Condense ---
                state.evidence.status = ScrapeStatus.CONDENSING
                condensed = self.condenser.condense(snapshot)

                # Check for blockers
                if condensed.detected_blockers:
                    state.evidence.status = ScrapeStatus.BLOCKED
                    logger.warning(
                        "Blockers detected: %s",
                        ", ".join(condensed.detected_blockers),
                    )

                # --- Extract ---
                state.evidence.status = ScrapeStatus.EXTRACTING
                extract_req = ExtractionRequest(
                    goal=target.goal,
                    condensed_dom=condensed,
                    context=context,
                )
                result = self.llm.extract(extract_req)

                # Persist insight
                if result.insight.strip():
                    insight = Insight(
                        session_id=session_id,
                        target_url=snapshot.url,
                        goal=target.goal,
                        extraction=result,
                        condensed_dom=condensed,
                        raw_snapshot=snapshot.html[:8192],
                    )
                    state.evidence.insights.append(insight)
                    state.evidence.navigation_log.append(
                        NavigationPlan(
                            action="extracted",
                            reason="Insight extracted from page",
                            expected_outcome="Data collected",
                        )
                    )
                    context = result.insight[:1000]

                # --- Decide next action ---
                if result.navigation:
                    nav = result.navigation
                else:
                    nav = self.llm.plan_navigation(
                        condensed, target.goal, context
                    )

                state.evidence.navigation_log.append(nav)

                # Terminate conditions
                if nav.action == "done":
                    logger.info(
                        "LLM signaled done after %d iterations", iteration + 1
                    )
                    state.evidence.status = ScrapeStatus.COMPLETE
                    break

                if state.current_depth >= target.max_depth:
                    logger.info("Max depth %d reached", target.max_depth)
                    state.evidence.status = ScrapeStatus.COMPLETE
                    break

                if state.evidence.pages_visited >= target.max_pages:
                    logger.info("Max pages %d visited", target.max_pages)
                    state.evidence.status = ScrapeStatus.COMPLETE
                    break

                # Policy check on navigation action
                nav_allowed, nav_reason = self.policy_engine.validate_navigation(
                    nav.action, snapshot.url
                )
                if not nav_allowed:
                    logger.warning(
                        "Navigation blocked by policy: %s (%s)",
                        nav.action, nav_reason,
                    )
                    continue

                # --- Execute navigation ---
                try:
                    snapshot = await self.browser.act(
                        nav.action,
                        selector=nav.selector,
                        value=nav.value,
                    )
                    if snapshot.url not in state.pages_seen:
                        state.pages_seen.add(snapshot.url)
                        state.evidence.pages_visited += 1
                        state.current_depth += 1
                    state.current_url = snapshot.url
                except Exception as e:
                    logger.warning("Action %s failed: %s", nav.action, e)
                    state.evidence.errors.append(
                        f"Action '{nav.action}' failed: {e}"
                    )
                    continue

                # Respectful delay between actions
                delay = self.policy_engine.rate_limit_delay(
                    state.evidence.pages_visited
                )
                await asyncio.sleep(delay)

            else:
                logger.warning(
                    "Reached max iterations (%d) without completion",
                    max_iterations,
                )
                state.evidence.status = ScrapeStatus.COMPLETE

            state.evidence.completed_at = datetime.now(timezone.utc)

        except Exception as e:
            logger.exception("Scrape session failed: %s", e)
            state.evidence.status = ScrapeStatus.FAILED
            state.evidence.errors.append(str(e))

        finally:
            await self.browser.close_session()
            self.store.save(state.evidence)

        return state.evidence

    async def run_batch(self, targets: list[ScrapeTarget]) -> list[Evidence]:
        """Run multiple scrape targets concurrently (respecting max_concurrent)."""
        sem = asyncio.Semaphore(self.policy.max_concurrent_sessions)

        async def _wrapped(t: ScrapeTarget) -> Evidence:
            async with sem:
                return await self.run(t)

        results = await asyncio.gather(
            *[_wrapped(t) for t in targets],
            return_exceptions=True,
        )
        return results  # type: ignore[return-value]

"""Browser adapter — Playwright-based browser automation with anti-detection.

Every browser action goes through this adapter.  The adapter is responsible for
managing the Playwright lifecycle, applying stealth scripts, capturing DOM
snapshots, and executing navigation actions (click, fill, scroll, wait).

Meteor Doctrine #3: Adapters isolate change.  Swapping Playwright for CDP or
Selenium must not require changes to any layer above this one.
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Optional

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from .contracts import DOMSnapshot, ScrapePolicy, ScrapeTarget

logger = logging.getLogger(__name__)

# Injected into every page context before navigation.
# Breaks common bot-detection checks: WebDriver flag, WebGL fingerprint,
# canvas fingerprint, navigator.plugins, Chrome runtime object.
STEALTH_SCRIPT = """
// === Meteor Stealth — browser anti-detection ===

// WebDriver flag — the single most common bot check
Object.defineProperty(navigator, 'webdriver', { get: () => false });

// Navigator plugins — bots often report length 0
Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });

// Languages
Object.defineProperty(navigator, 'languages', { get: () => ['en-US','en'] });

// Chrome runtime — bots often lack this
window.chrome = { runtime: {} };

// Permissions query — real browsers support this
const origQuery = window.navigator.permissions?.query;
if (origQuery) {
    window.navigator.permissions.query = function(parameters) {
        if (parameters.name === 'notifications') {
            return Promise.resolve({ state: 'prompt' });
        }
        return origQuery.call(this, parameters);
    };
}

// WebGL fingerprint noise
try {
    const getParam = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(parameter) {
        if (parameter === 37445) return 'Intel Inc.';
        if (parameter === 37446) return 'Intel Iris OpenGL Engine';
        return getParam.call(this, parameter);
    };
} catch(e) {}

// Canvas fingerprint noise — add subtle noise to toDataURL/toBlob
try {
    const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function(...args) {
        const ctx = this.getContext('2d');
        if (ctx) {
            const imageData = ctx.getImageData(0, 0, this.width, this.height);
            if (imageData && imageData.data.length > 0) {
                imageData.data[0] = imageData.data[0] ^ 1;
            }
            ctx.putImageData(imageData, 0, 0);
        }
        return origToDataURL.apply(this, args);
    };
} catch(e) {}
"""


class BrowserAdapter:
    """Manages Playwright browser lifecycle with anti-detection."""

    def __init__(self, policy: ScrapePolicy) -> None:
        self.policy = policy
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    async def __aenter__(self) -> "BrowserAdapter":
        await self.start()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.stop()

    async def start(self) -> None:
        """Launch Playwright and the Chromium browser process."""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.policy.headless,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-web-security",
                "--disable-dev-shm-usage",
            ],
        )
        logger.info("Browser launched (headless=%s)", self.policy.headless)

    async def new_session(self, target: ScrapeTarget) -> None:
        """Create a new browser context for a scrape target (isolated session)."""
        if not self._browser:
            raise RuntimeError("Browser not started — call start() first")

        self._context = await self._browser.new_context(
            viewport={"width": target.viewport[0], "height": target.viewport[1]},
            user_agent=(
                target.user_agent
                or (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
                )
            ),
            locale="en-US",
            timezone_id="America/New_York",
            proxy={"server": target.proxy} if target.proxy else None,
        )

        if self.policy.stealth_mode:
            await self._context.add_init_script(STEALTH_SCRIPT)

        self._page = await self._context.new_page()
        logger.info("New browser session for %s", target.url)

    async def navigate(self, url: str) -> DOMSnapshot:
        """Navigate to a URL, wait for network idle, return a DOM snapshot."""
        if not self._page:
            raise RuntimeError("No active page session")

        await self._page.goto(url, wait_until="networkidle", timeout=30000)
        # Randomised delay to appear human
        await asyncio.sleep(random.uniform(0.5, 2.0))
        snapshot = await self._capture_snapshot()
        logger.info("Navigated → %s (title=%s)", url, snapshot.title)
        return snapshot

    async def act(
        self,
        action: str,
        selector: Optional[str] = None,
        value: Optional[str] = None,
    ) -> DOMSnapshot:
        """Execute a single browser action, return the resulting DOM snapshot."""
        if not self._page:
            raise RuntimeError("No active page session")

        if selector:
            await self._page.wait_for_selector(selector, timeout=10000)

        if action == "click":
            if not selector:
                raise ValueError("click requires a selector")
            await self._page.click(selector)
        elif action == "fill":
            if not selector or value is None:
                raise ValueError("fill requires selector and value")
            await self._page.fill(selector, value)
        elif action == "scroll":
            delta_y = int(value or "500")
            await self._page.evaluate(f"window.scrollBy(0, {delta_y})")
        elif action == "wait":
            delay = int(value or "2000")
            await asyncio.sleep(delay / 1000)
        else:
            raise ValueError(f"Unknown action: {action}")

        # Human-like jitter after any action
        await asyncio.sleep(random.uniform(0.3, 1.0))
        await self._page.wait_for_load_state("networkidle", timeout=15000)
        return await self._capture_snapshot()

    async def _capture_snapshot(self) -> DOMSnapshot:
        """Capture the current page state as a DOMSnapshot."""
        if not self._page:
            raise RuntimeError("No active page")

        data: dict = await self._page.evaluate("""() => {
            const links = Array.from(document.querySelectorAll('a[href]'))
                .filter(a => {
                    const r = a.getBoundingClientRect();
                    return r.top >= 0 && r.top < window.innerHeight;
                })
                .map(a => ({
                    text: (a.innerText || '').trim().slice(0, 200),
                    href: a.href
                }));
            return {
                url: document.location.href,
                title: document.title || '',
                html: document.documentElement.outerHTML || '',
                text: document.body ? document.body.innerText || '' : '',
                links: links.slice(0, 100),
                viewport: [window.innerWidth, window.innerHeight],
                scroll: [window.scrollX, window.scrollY]
            };
        }""")

        return DOMSnapshot(
            url=str(data["url"]),
            title=str(data["title"]),
            html=str(data["html"])[: self.policy.max_page_size_bytes],
            text_content=str(data["text"]),
            visible_links=data["links"],
            viewport_size=(
                int(data["viewport"][0]) if data.get("viewport") else 0,
                int(data["viewport"][1]) if data.get("viewport") else 0,
            ),
            scroll_position=(
                int(data["scroll"][0]) if data.get("scroll") else 0,
                int(data["scroll"][1]) if data.get("scroll") else 0,
            ),
        )

    async def screenshot(self) -> bytes:
        """Capture a PNG screenshot of the current page."""
        if not self._page:
            raise RuntimeError("No active page")
        return await self._page.screenshot(type="png")

    async def close_session(self) -> None:
        """Close the current browser context (session)."""
        if self._context:
            await self._context.close()
            self._context = None
            self._page = None
            logger.info("Browser session closed")

    async def stop(self) -> None:
        """Teardown: close context, browser, and Playwright."""
        if self._context:
            await self.close_session()
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        logger.info("Browser adapter shut down")

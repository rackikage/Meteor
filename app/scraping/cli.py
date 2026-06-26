"""CLI entry point for the Meteor scraper.

Usage:
  python -m app.scraping scrape <url> --goal "extract product prices"
  python -m app.scraping list
  python -m app.scraping view <file>
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Optional

from .browser_adapter import BrowserAdapter
from .condenser import DOMCondenser
from .contracts import ScrapePolicy, ScrapeTarget
from .llm_adapter import LLMAdapter
from .orchestrator import ScrapingOrchestrator
from .policy import PolicyEngine
from .storage import EvidenceStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("meteor.scraper")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="meteor-scrape",
        description="Meteor Scraper — LLM-driven agentic insight extraction",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # scrape
    scrape = sub.add_parser("scrape", help="Run a scraping session")
    scrape.add_argument("url", help="Target URL")
    scrape.add_argument(
        "--goal", "-g", required=True, help="Extraction goal in natural language"
    )
    scrape.add_argument("--depth", type=int, default=3, help="Max navigation depth")
    scrape.add_argument("--pages", type=int, default=10, help="Max pages to visit")
    scrape.add_argument(
        "--delay", type=int, default=1500, help="Delay between requests (ms)"
    )
    scrape.add_argument(
        "--headful", action="store_true", help="Show browser window"
    )
    scrape.add_argument(
        "--model", default="llama3.2:3b", help="Ollama model name"
    )
    scrape.add_argument(
        "--proxy", help="Proxy URL (e.g. http://user:pass@host:port)"
    )
    scrape.add_argument(
        "--output", "-o", help="Output file path"
    )

    # list
    list_cmd = sub.add_parser("list", help="List completed scraping sessions")
    list_cmd.add_argument(
        "--dir", default="~/.meteor/evidence", help="Evidence directory"
    )

    # view
    view = sub.add_parser("view", help="View a saved evidence file")
    view.add_argument("file", help="Evidence file path or session ID")

    return parser


async def _cmd_scrape(args: argparse.Namespace) -> None:
    policy = ScrapePolicy(
        headless=not args.headful,
        request_delay_ms=args.delay,
    )
    target = ScrapeTarget(
        url=args.url,
        goal=args.goal,
        max_depth=args.depth,
        max_pages=args.pages,
        proxy=args.proxy,
    )

    policy_engine = PolicyEngine(policy)
    allowed, reason = policy_engine.validate_target(target)
    if not allowed:
        logger.error("Target rejected by policy: %s", reason)
        sys.exit(1)

    browser = BrowserAdapter(policy)
    condenser = DOMCondenser(policy)
    llm = LLMAdapter(model=args.model)
    store = EvidenceStore()

    orchestrator = ScrapingOrchestrator(
        browser, condenser, llm, policy, policy_engine, store,
    )
    evidence = await orchestrator.run(target)

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Session complete: {evidence.status.value}")
    print(f"Pages visited: {evidence.pages_visited}")
    print(f"Insights collected: {len(evidence.insights)}")
    print(f"Errors: {len(evidence.errors)}")
    print("\nInsights:")
    for i, insight in enumerate(evidence.insights, 1):
        print(
            f"  {i}. [{insight.extraction.confidence:.0%}] "
            f"{insight.condensed_dom.url}"
        )
        print(f"     {insight.extraction.insight[:200]}...")
    if evidence.errors:
        print("\nErrors:")
        for err in evidence.errors:
            print(f"  - {err}")
    print(f"{'=' * 60}")

    if args.output:
        with open(args.output, "w") as f:
            f.write(evidence.model_dump_json(indent=2))
        print(f"Written to {args.output}")


async def _cmd_list(args: argparse.Namespace) -> None:
    store = EvidenceStore(args.dir)
    sessions = store.list_sessions()
    if not sessions:
        print("No sessions found.")
        return
    header = f"{'Session ID':<20} {'URL':<40} {'Status':<12} {'Pg':<5} {'Ins':<5}"
    print(header)
    print("-" * 86)
    for s in sessions[:30]:
        print(
            f"{s['session_id'][:18]:<20} "
            f"{s['url'][:38]:<40} "
            f"{s['status']:<12} "
            f"{s['pages']:<5} "
            f"{s['insights']:<5}"
        )


async def _cmd_view(args: argparse.Namespace) -> None:
    store = EvidenceStore()
    fp = Path(args.file)
    evidence: Optional[Evidence] = None

    if fp.exists():
        evidence = store.load(fp)
    else:
        for f in store.storage_dir.glob("*.json"):
            data = json.loads(f.read_text())
            if data.get("session_id") == args.file:
                evidence = store.load(f)
                break

    if evidence is None:
        logger.error("No evidence found matching '%s'", args.file)
        sys.exit(1)

    print(evidence.model_dump_json(indent=2))


def cli() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "scrape":
        asyncio.run(_cmd_scrape(args))
    elif args.command == "list":
        asyncio.run(_cmd_list(args))
    elif args.command == "view":
        asyncio.run(_cmd_view(args))

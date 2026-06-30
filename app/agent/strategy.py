"""LLM-adaptive scan strategy engine — the meta-learning layer.

Consults the local Ollama model between scan phases to adapt port selection,
pivot ordering, and technique based on what has already been discovered.

Memory
──────
Strategy decisions and their outcomes are stored in the audit SQLite database.
On each call the engine loads the last N outcomes and includes them in the
prompt, creating a feedback loop where the model's recommendations improve over
successive runs ("meta-learning").

Graceful degradation
────────────────────
If Ollama is offline the engine returns DEFAULT_STRATEGY so the agent always
has a sensible fallback.

Meteor Doctrine #7: Evidence precedes conclusions.
Meteor Doctrine #10: Every component must be replaceable.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


STRATEGY_PROMPT = """\
You are Meteor's scan strategist. Your job is to decide what to probe next \
to maximise attack-surface discovery.

=== PAST OUTCOMES (last {n_history} runs) ===
{history}

=== CURRENT FINDINGS ===
Depth level : {depth}
Hosts found : {hosts_found}

Services discovered:
{services}

CVEs matched:
{cves}

=== INSTRUCTIONS ===
Return a single JSON object — no markdown, no explanation outside the JSON:
{{
  "next_ports": [<up to 25 port ints>],
  "pivot_targets": [<up to 10 IP strings, or []>],
  "technique": "<syn|connect>",
  "priority_services": [<service name strings>],
  "skip_ports": [<ports to skip because they are confirmed closed>],
  "reason": "<one sentence>"
}}
"""


@dataclass
class ScanStrategy:
    next_ports: list[int] = field(default_factory=lambda: [
        21, 22, 23, 25, 53, 80, 110, 111, 135, 139, 143,
        443, 445, 993, 3306, 3389, 5432, 5900, 6379, 8080, 8443,
    ])
    pivot_targets: list[str] = field(default_factory=list)
    technique: str = "connect"
    priority_services: list[str] = field(default_factory=list)
    skip_ports: list[int] = field(default_factory=list)
    reason: str = "default"
    llm_adapted: bool = False


DEFAULT_STRATEGY = ScanStrategy()


@dataclass
class _Outcome:
    timestamp: str
    hosts: int
    services: int
    critical_vulns: int
    ports_used: list[int]
    depth: int


class StrategyEngine:
    """Queries the free Ollama model to adapt scan strategy from live results.

    Usage:
        engine = StrategyEngine(model="llama3.2")
        strategy = await engine.decide(
            hosts_found=["10.0.0.1"],
            services=[{"ip": "10.0.0.1", "port": 22, "name": "ssh"}],
            cves=[{"cve_id": "CVE-2023-0001", "severity": "HIGH"}],
            depth=1,
        )
        # Use strategy.next_ports, strategy.pivot_targets, etc.
    """

    def __init__(
        self,
        model: str = "llama3.2",
        base_url: str = "http://localhost:11434",
        timeout: float = 20.0,
        history_size: int = 5,
        storage=None,
    ) -> None:
        self._model = model
        self._base = base_url
        self._timeout = timeout
        self._history_size = history_size
        self._storage = storage  # optional SQLiteAdapter for outcome memory

    # ── Public ───────────────────────────────────────────────────────

    async def decide(
        self,
        hosts_found: list[str],
        services: list[dict],
        cves: list[dict],
        depth: int,
    ) -> ScanStrategy:
        """Consult the LLM for next-step recommendations."""
        history = self._load_history()
        prompt = self._build_prompt(hosts_found, services, cves, depth, history)

        try:
            strategy = await self._call_llm(prompt)
            logger.info(
                "Strategy [LLM]: %s (ports=%d, pivots=%d)",
                strategy.reason[:80],
                len(strategy.next_ports),
                len(strategy.pivot_targets),
            )
            return strategy
        except Exception as e:
            logger.debug("Strategy LLM call failed (%s) — using default", e)
            return DEFAULT_STRATEGY

    def record_outcome(
        self,
        hosts: int,
        services: int,
        critical_vulns: int,
        ports_used: list[int],
        depth: int,
    ) -> None:
        """Persist a scan outcome so future decisions can learn from it."""
        if self._storage is None:
            return
        try:
            now = datetime.now(timezone.utc).isoformat()
            self._storage.execute(
                """
                INSERT INTO strategy_outcomes
                  (timestamp, hosts, services, critical_vulns, ports_json, depth)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (now, hosts, services, critical_vulns, json.dumps(ports_used), depth),
                store="audit",
            )
        except Exception as e:
            logger.debug("Could not persist strategy outcome: %s", e)

    def ensure_table(self) -> None:
        """Create the strategy_outcomes table if it does not exist."""
        if self._storage is None:
            return
        try:
            self._storage.execute(
                """
                CREATE TABLE IF NOT EXISTS strategy_outcomes (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp    TEXT NOT NULL,
                    hosts        INTEGER DEFAULT 0,
                    services     INTEGER DEFAULT 0,
                    critical_vulns INTEGER DEFAULT 0,
                    ports_json   TEXT DEFAULT '[]',
                    depth        INTEGER DEFAULT 0
                )
                """,
                store="audit",
            )
        except Exception as e:
            logger.debug("Could not create strategy_outcomes table: %s", e)

    # ── Private ──────────────────────────────────────────────────────

    def _load_history(self) -> list[_Outcome]:
        if self._storage is None:
            return []
        try:
            rows = self._storage.execute(
                """
                SELECT timestamp, hosts, services, critical_vulns, ports_json, depth
                FROM strategy_outcomes
                ORDER BY id DESC LIMIT ?
                """,
                (self._history_size,),
                store="audit",
            )
            return [
                _Outcome(
                    timestamp=r["timestamp"],
                    hosts=r["hosts"],
                    services=r["services"],
                    critical_vulns=r["critical_vulns"],
                    ports_used=json.loads(r["ports_json"]),
                    depth=r["depth"],
                )
                for r in rows
            ]
        except Exception:
            return []

    def _build_prompt(
        self,
        hosts: list[str],
        services: list[dict],
        cves: list[dict],
        depth: int,
        history: list[_Outcome],
    ) -> str:
        history_str = "  (no prior runs yet)"
        if history:
            lines = []
            for o in history:
                lines.append(
                    f"  [{o.timestamp[:10]}] depth={o.depth} "
                    f"hosts={o.hosts} services={o.services} "
                    f"criticals={o.critical_vulns} "
                    f"ports={o.ports_used[:8]}{'...' if len(o.ports_used) > 8 else ''}"
                )
            history_str = "\n".join(lines)

        svc_str = "\n".join(
            f"  {s.get('ip','?')}:{s.get('port','?')} "
            f"{s.get('name','unknown')} {s.get('banner','')[:50]}"
            for s in services[:20]
        ) or "  (none)"

        cve_str = "\n".join(
            f"  {c.get('cve_id','?')} [{c.get('severity','?')}] "
            f"{c.get('description','')[:80]}"
            for c in cves[:10]
        ) or "  (none)"

        return STRATEGY_PROMPT.format(
            n_history=len(history),
            history=history_str,
            depth=depth,
            hosts_found=len(hosts),
            services=svc_str,
            cves=cve_str,
        )

    async def _call_llm(self, prompt: str) -> ScanStrategy:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base}/api/generate",
                json={
                    "model": self._model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 512},
                },
            )
            resp.raise_for_status()
            raw = resp.json().get("response", "")

        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end <= start:
            raise ValueError("LLM returned no JSON object")

        data = json.loads(raw[start:end])

        return ScanStrategy(
            next_ports=[int(p) for p in data.get("next_ports", []) if 1 <= int(p) <= 65535][:25],
            pivot_targets=[str(ip) for ip in data.get("pivot_targets", [])][:10],
            technique=data.get("technique", "connect"),
            priority_services=data.get("priority_services", []),
            skip_ports=[int(p) for p in data.get("skip_ports", [])][:50],
            reason=str(data.get("reason", ""))[:200],
            llm_adapted=True,
        )

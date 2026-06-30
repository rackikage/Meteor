"""LLM-adaptive scan strategy engine — the meta-learning layer.

Consults the local Ollama model between scan phases to adapt port selection,
pivot ordering, and technique based on what has already been discovered.

Behavior Vector (BV)
────────────────────
Every scan is fingerprinted into a compact BehaviorVector: host count, service
types, vuln severity, ports tried.  At decision time the engine finds the top-k
most similar past BVs from SQLite history, ranks them by reward (intel density
per port probed), and injects them as in-context examples into the Ollama prompt.
That is the meta-learning feedback loop — the model sees "for a target like this,
port set X yielded reward Y" and can generalise.

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
from dataclasses import asdict, dataclass, field, fields as dc_fields
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


# ── Behavior Vector ──────────────────────────────────────────────────────────

@dataclass
class BehaviorVector:
    """Compact numerical fingerprint of a scan's context and results.

    Used for meta-learning: past scans with similar BVs are surfaced as
    in-context examples so the LLM can generalise across target types.
    """
    n_hosts: int = 0
    n_services: int = 0
    n_criticals: int = 0
    n_highs: int = 0
    depth: int = 0
    ports_tried: int = 0
    has_ssh: int = 0       # 0 / 1 (bool-as-int for JSON compat)
    has_http: int = 0
    has_smb: int = 0
    has_rdp: int = 0
    has_db: int = 0        # any db: mysql/postgres/mongo/redis/mssql

    def to_vec(self) -> list[float]:
        """Normalised float vector for cosine similarity."""
        return [
            self.n_hosts     / 10.0,
            self.n_services  / 20.0,
            self.n_criticals /  5.0,
            self.n_highs     / 10.0,
            self.depth       /  3.0,
            self.ports_tried / 100.0,
            float(self.has_ssh),
            float(self.has_http),
            float(self.has_smb),
            float(self.has_rdp),
            float(self.has_db),
        ]

    def reward(self) -> float:
        """Intel density per port probed — the meta-learning reward signal."""
        if self.ports_tried == 0:
            return 0.0
        score = self.n_services + self.n_criticals * 3.0 + self.n_highs * 1.5
        return round(min(score / self.ports_tried, 10.0), 3)

    def label(self) -> str:
        """Human-readable summary for prompt injection."""
        parts = [
            s for s, flag in [
                ("SSH", self.has_ssh), ("HTTP", self.has_http),
                ("SMB", self.has_smb), ("RDP", self.has_rdp), ("DB", self.has_db),
            ] if flag
        ]
        svc_label = "+".join(parts) if parts else "unknown"
        return (
            f"{svc_label} | hosts={self.n_hosts} svcs={self.n_services} "
            f"crit={self.n_criticals} high={self.n_highs} "
            f"ports_tried={self.ports_tried}"
        )


def bv_from_scan(
    hosts: list[str],
    services: list[dict],
    cves: list[dict],
    ports: list[int],
    depth: int,
) -> BehaviorVector:
    """Build a BehaviorVector from live scan results."""
    names = {s.get("name", "").lower() for s in services}
    db_names = {"mysql", "postgresql", "mongodb", "redis", "mssql", "oracle"}
    return BehaviorVector(
        n_hosts=len(set(hosts)),
        n_services=len(services),
        n_criticals=sum(1 for c in cves if c.get("severity") == "CRITICAL"),
        n_highs=sum(1 for c in cves if c.get("severity") == "HIGH"),
        depth=depth,
        ports_tried=len(ports),
        has_ssh=int("ssh" in names),
        has_http=int(bool({"http", "https", "http-proxy", "https-alt"} & names)),
        has_smb=int("smb" in names or "netbios" in names),
        has_rdp=int("rdp" in names),
        has_db=int(bool(db_names & names)),
    )


def _bv_cosine(a: BehaviorVector, b: BehaviorVector) -> float:
    """Cosine similarity between two BehaviorVectors (0–1)."""
    va, vb = a.to_vec(), b.to_vec()
    dot = sum(x * y for x, y in zip(va, vb))
    na = sum(x * x for x in va) ** 0.5
    nb = sum(x * x for x in vb) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# ── Strategy types ───────────────────────────────────────────────────────────

STRATEGY_PROMPT = """\
You are Meteor's scan strategist. Decide what to probe next to maximise \
attack-surface discovery.

=== BEHAVIOR VECTOR (current target profile) ===
{bv_label}

=== SIMILAR PAST SCANS (by BV similarity, highest reward first) ===
{similar_history}

=== RECENT HISTORY (last {n_history} runs) ===
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
    bv: Optional[BehaviorVector] = None
    reward: float = 0.0


# ── Engine ───────────────────────────────────────────────────────────────────

class StrategyEngine:
    """Queries the free Ollama model to adapt scan strategy from live results.

    Meta-learning loop:
      1. bv_from_scan() fingerprints the current target state.
      2. _find_similar() retrieves top-k past BVs by cosine similarity.
      3. Similar examples (ranked by reward) are injected into the prompt.
      4. record_outcome() writes this scan's BV + reward to SQLite.
      5. Next run's decide() picks it up as a training example.

    Usage:
        engine = StrategyEngine(model="llama3.2")
        bv = bv_from_scan(hosts, services, cves, ports, depth)
        strategy = await engine.decide(hosts, services, cves, depth, bv=bv)
        # ... run the scan ...
        engine.record_outcome(hosts, services, criticals, ports, depth, bv=bv)
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
        self._storage = storage

    # ── Public ───────────────────────────────────────────────────────────────

    async def decide(
        self,
        hosts_found: list[str],
        services: list[dict],
        cves: list[dict],
        depth: int,
        bv: Optional[BehaviorVector] = None,
    ) -> ScanStrategy:
        """Consult the LLM for next-step recommendations."""
        history = self._load_history()
        prompt = self._build_prompt(hosts_found, services, cves, depth, history, bv)

        try:
            strategy = await self._call_llm(prompt)
            logger.info(
                "Strategy [LLM | bv_reward=%.2f]: %s (ports=%d, pivots=%d)",
                bv.reward() if bv else 0.0,
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
        bv: Optional[BehaviorVector] = None,
    ) -> None:
        """Persist a scan outcome so future decisions can learn from it."""
        if self._storage is None:
            return
        try:
            now = datetime.now(timezone.utc).isoformat()
            reward = bv.reward() if bv else 0.0
            bv_json = json.dumps(asdict(bv)) if bv else "{}"
            self._storage.execute(
                """
                INSERT INTO strategy_outcomes
                  (timestamp, hosts, services, critical_vulns, ports_json,
                   depth, bv_json, reward)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (now, hosts, services, critical_vulns,
                 json.dumps(ports_used), depth, bv_json, reward),
                store="audit",
            )
            logger.debug("Outcome recorded: reward=%.3f bv=%s", reward,
                         bv.label() if bv else "none")
        except Exception as e:
            logger.debug("Could not persist strategy outcome: %s", e)

    def ensure_table(self) -> None:
        """Create the strategy_outcomes table (and migrate existing schemas)."""
        if self._storage is None:
            return
        try:
            self._storage.execute(
                """
                CREATE TABLE IF NOT EXISTS strategy_outcomes (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp      TEXT NOT NULL,
                    hosts          INTEGER DEFAULT 0,
                    services       INTEGER DEFAULT 0,
                    critical_vulns INTEGER DEFAULT 0,
                    ports_json     TEXT DEFAULT '[]',
                    depth          INTEGER DEFAULT 0,
                    bv_json        TEXT DEFAULT '{}',
                    reward         REAL DEFAULT 0.0
                )
                """,
                store="audit",
            )
            # Non-fatal migrations for databases that existed before BV columns
            for col, coltype, default in [
                ("bv_json", "TEXT", "'{}'"),
                ("reward",  "REAL", "0.0"),
            ]:
                try:
                    self._storage.execute(
                        f"ALTER TABLE strategy_outcomes ADD COLUMN "
                        f"{col} {coltype} DEFAULT {default}",
                        store="audit",
                    )
                except Exception:
                    pass  # column already present
        except Exception as e:
            logger.debug("Could not create strategy_outcomes table: %s", e)

    # ── Private ──────────────────────────────────────────────────────────────

    def _load_history(self) -> list[_Outcome]:
        if self._storage is None:
            return []
        try:
            rows = self._storage.execute(
                """
                SELECT timestamp, hosts, services, critical_vulns, ports_json,
                       depth, bv_json, reward
                FROM strategy_outcomes
                ORDER BY id DESC LIMIT ?
                """,
                (self._history_size * 4,),   # load extra for BV retrieval pool
                store="audit",
            )
            bv_field_names = {f.name for f in dc_fields(BehaviorVector)}
            outcomes = []
            for r in rows:
                bv: Optional[BehaviorVector] = None
                try:
                    bv_data = json.loads(r.get("bv_json") or "{}")
                    if bv_data:
                        bv = BehaviorVector(
                            **{k: v for k, v in bv_data.items()
                               if k in bv_field_names}
                        )
                except Exception:
                    pass
                outcomes.append(_Outcome(
                    timestamp=r["timestamp"],
                    hosts=r["hosts"],
                    services=r["services"],
                    critical_vulns=r["critical_vulns"],
                    ports_used=json.loads(r["ports_json"]),
                    depth=r["depth"],
                    bv=bv,
                    reward=r.get("reward", 0.0),
                ))
            return outcomes
        except Exception:
            return []

    @staticmethod
    def _find_similar(
        current_bv: BehaviorVector,
        all_outcomes: list[_Outcome],
        n: int = 3,
    ) -> list[_Outcome]:
        """Return past outcomes whose BV is most similar to the current scan.

        Ranked by (cosine_similarity DESC, reward DESC) so the LLM sees the
        most relevant AND highest-quality past examples first.
        """
        scored = [
            (_bv_cosine(current_bv, o.bv), o)
            for o in all_outcomes
            if o.bv is not None
        ]
        scored.sort(key=lambda x: (x[0], x[1].reward), reverse=True)
        return [o for _, o in scored[:n]]

    def _build_prompt(
        self,
        hosts: list[str],
        services: list[dict],
        cves: list[dict],
        depth: int,
        history: list[_Outcome],
        current_bv: Optional[BehaviorVector] = None,
    ) -> str:
        recent = history[: self._history_size]

        history_str = "  (no prior runs yet)"
        if recent:
            lines = []
            for o in recent:
                lines.append(
                    f"  [{o.timestamp[:10]}] depth={o.depth} "
                    f"hosts={o.hosts} services={o.services} "
                    f"criticals={o.critical_vulns} reward={o.reward:.2f} "
                    f"ports={o.ports_used[:6]}{'...' if len(o.ports_used) > 6 else ''}"
                )
            history_str = "\n".join(lines)

        bv_label = current_bv.label() if current_bv else "(no BV — first run)"

        similar_str = "  (not enough history yet)"
        if current_bv and history:
            similar = self._find_similar(current_bv, history, n=3)
            if similar:
                lines = []
                for o in similar:
                    lbl = o.bv.label() if o.bv else "?"
                    lines.append(
                        f"  [{o.timestamp[:10]}] {lbl} | "
                        f"ports={o.ports_used[:6]}"
                        f"{'...' if len(o.ports_used) > 6 else ''} "
                        f"→ reward={o.reward:.2f}"
                    )
                similar_str = "\n".join(lines)

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
            bv_label=bv_label,
            similar_history=similar_str,
            n_history=len(recent),
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
            next_ports=[int(p) for p in data.get("next_ports", [])
                        if 1 <= int(p) <= 65535][:25],
            pivot_targets=[str(ip) for ip in data.get("pivot_targets", [])][:10],
            technique=data.get("technique", "connect"),
            priority_services=data.get("priority_services", []),
            skip_ports=[int(p) for p in data.get("skip_ports", [])][:50],
            reason=str(data.get("reason", ""))[:200],
            llm_adapted=True,
        )

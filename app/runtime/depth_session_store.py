"""Persistent depth-session store for multi-turn infiltration ops."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from app.runtime.depth_context import DepthSession, DepthStep

logger = logging.getLogger(__name__)

SESSION_DIR = Path.home() / ".meteor" / "sessions"


@dataclass
class SessionFindings:
    """Lightweight findings carried across follow-up turns."""

    gateway: str = ""
    cidr: str = ""
    hosts_discovered: int = 0
    services_discovered: int = 0
    top_services: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class StoredDepthSession:
    session_id: str
    max_depth: int
    steps: list[dict] = field(default_factory=list)
    findings: dict = field(default_factory=dict)

    def to_depth_session(self) -> DepthSession:
        session = DepthSession(max_depth=self.max_depth)
        for raw in self.steps:
            session.steps.append(
                DepthStep(
                    name=raw.get("name", "step"),
                    output=raw.get("output", ""),
                    summary=raw.get("summary", ""),
                )
            )
        return session

    @classmethod
    def from_depth_session(cls, session_id: str, session: DepthSession, findings: SessionFindings) -> StoredDepthSession:
        return cls(
            session_id=session_id,
            max_depth=session.max_depth,
            steps=[
                {"name": s.name, "output": s.output, "summary": s.summary}
                for s in session.steps
            ],
            findings=asdict(findings),
        )


class DepthSessionStore:
    """In-memory cache with JSON persistence keyed by conversation ID."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self._base = base_dir or SESSION_DIR
        self._cache: dict[str, StoredDepthSession] = {}

    def _path(self, session_id: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in session_id)
        return self._base / f"{safe}.json"

    def load(self, session_id: str) -> Optional[StoredDepthSession]:
        if session_id in self._cache:
            return self._cache[session_id]

        path = self._path(session_id)
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            stored = StoredDepthSession(
                session_id=raw["session_id"],
                max_depth=raw.get("max_depth", 2),
                steps=raw.get("steps", []),
                findings=raw.get("findings", {}),
            )
            self._cache[session_id] = stored
            return stored
        except (OSError, json.JSONDecodeError, KeyError) as exc:
            logger.warning("Failed to load depth session %s: %s", session_id, exc)
            return None

    def save(self, stored: StoredDepthSession) -> None:
        self._cache[stored.session_id] = stored
        self._base.mkdir(parents=True, exist_ok=True)
        path = self._path(stored.session_id)
        path.write_text(json.dumps(asdict(stored), indent=2), encoding="utf-8")

    def get_or_create(self, session_id: str, max_depth: int = 2) -> StoredDepthSession:
        existing = self.load(session_id)
        if existing is not None:
            existing.max_depth = max(existing.max_depth, max_depth)
            return existing
        stored = StoredDepthSession(session_id=session_id, max_depth=max_depth)
        self.save(stored)
        return stored

    def update_from_depth_session(
        self,
        session_id: str,
        depth_session: DepthSession,
        findings: SessionFindings,
    ) -> None:
        stored = StoredDepthSession.from_depth_session(session_id, depth_session, findings)
        self.save(stored)

    def context_block(self, session_id: str) -> str:
        """Text block for LLM intent routing and chat context."""
        stored = self.load(session_id)
        if stored is None:
            return ""

        lines = ["Recent infiltration session:"]
        findings = stored.findings
        if findings.get("gateway"):
            lines.append(f"  gateway: {findings['gateway']}")
        if findings.get("cidr"):
            lines.append(f"  subnet: {findings['cidr']}")
        if findings.get("hosts_discovered"):
            lines.append(f"  hosts: {findings['hosts_discovered']}")
        if findings.get("services_discovered"):
            lines.append(f"  services: {findings['services_discovered']}")
        if findings.get("top_services"):
            lines.append(f"  top services: {', '.join(findings['top_services'][:8])}")
        for step in stored.steps[-4:]:
            summary = step.get("summary") or step.get("output", "")[:120]
            lines.append(f"  [{step.get('name', 'step')}] {summary}")
        for note in (findings.get("notes") or [])[-3:]:
            lines.append(f"  note: {note}")
        return "\n".join(lines)


# Process-wide singleton for GUI + runtime
_store: DepthSessionStore | None = None


def get_depth_session_store() -> DepthSessionStore:
    global _store
    if _store is None:
        _store = DepthSessionStore()
    return _store

"""Evidence store — persists scraping evidence to disk.

Meteor Doctrine #7: Evidence precedes conclusions.
Meteor Doctrine #5: Memory is infrastructure.

The EvidenceStore is the persistable memory layer for scraping sessions.
It writes JSON artifacts to disk and can load them back for cross-session
correlation (the cross-reference adapter reads from here).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from .contracts import Evidence, Insight

logger = logging.getLogger(__name__)


class EvidenceStore:
    """Persists scraping evidence as versioned JSON artifacts on disk."""

    def __init__(self, storage_dir: str = "~/.meteor/evidence") -> None:
        self.storage_dir = Path(storage_dir).expanduser()
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Evidence store: %s", self.storage_dir)

    def save(self, evidence: Evidence) -> Path:
        """Persist evidence to a timestamped JSON file.  Returns the file path."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(
            c if c.isalnum() or c in "._-" else "_"
            for c in evidence.target.url
        )[:80]
        filename = f"{timestamp}__{safe_name}.json"
        filepath = self.storage_dir / filename

        serialised = self._serialize(evidence)
        with open(filepath, "w") as f:
            json.dump(serialised, f, indent=2, default=str)

        logger.info(
            "Evidence saved: %s (%d insights, %d pages)",
            filepath,
            len(evidence.insights),
            evidence.pages_visited,
        )
        return filepath

    def load(self, filepath: Path) -> Optional[Evidence]:
        """Load evidence from a previously saved JSON file."""
        if not filepath.exists():
            logger.warning("Evidence file not found: %s", filepath)
            return None

        with open(filepath) as f:
            data = json.load(f)

        return self._deserialize(data)

    def list_sessions(self) -> list[dict]:
        """List all completed sessions with summary metadata."""
        sessions = []
        for fp in sorted(self.storage_dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(fp.read_text())
                sessions.append({
                    "session_id": data.get("session_id", ""),
                    "url": data.get("target", {}).get("url", ""),
                    "status": data.get("status", "unknown"),
                    "pages": data.get("pages_visited", 0),
                    "insights": len(data.get("insights", [])),
                    "file": fp.name,
                    "saved_at": fp.stat().st_mtime,
                })
            except Exception as e:
                logger.warning("Failed to read %s: %s", fp.name, e)
        return sessions

    @staticmethod
    def _serialize(evidence: Evidence) -> dict:
        return {
            "session_id": evidence.session_id,
            "target": evidence.target.model_dump(),
            "insights": [i.model_dump() for i in evidence.insights],
            "navigation_log": [n.model_dump() for n in evidence.navigation_log],
            "status": evidence.status.value,
            "started_at": evidence.started_at.isoformat(),
            "completed_at": (
                evidence.completed_at.isoformat()
                if evidence.completed_at
                else None
            ),
            "pages_visited": evidence.pages_visited,
            "errors": evidence.errors,
        }

    @staticmethod
    def _deserialize(data: dict) -> Evidence:
        from .contracts import ScrapeStatus
        data["status"] = ScrapeStatus(data.get("status", "pending"))
        return Evidence(**data)

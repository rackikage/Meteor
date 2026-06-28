"""Health endpoint — runtime health checks and diagnostics.

Provides:
- GET /health — aggregated health status
- GET /health/components — per-component health
- GET /health/audit — recent audit log entries
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    status: str
    healthy: bool
    detail: str
    components: dict
    metadata: dict


class AuditLogResponse(BaseModel):
    entries: list[dict]
    count: int


@router.get("", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    """Get aggregated runtime health status."""
    from app.api.main import get_runtime
    runtime = get_runtime()

    health = runtime.observability.health()

    return HealthResponse(
        status="healthy" if health.healthy else "unhealthy",
        healthy=health.healthy,
        detail=health.detail,
        components=health.metadata.get("components", {}),
        metadata=health.metadata,
    )


@router.get("/components")
async def get_component_health():
    """Get per-component health status."""
    from app.api.main import get_runtime
    runtime = get_runtime()

    health = runtime.observability.health()
    return health.metadata.get("components", {})


@router.get("/audit", response_model=AuditLogResponse)
async def get_audit_log(limit: int = 100, event: Optional[str] = None) -> AuditLogResponse:
    """Get recent audit log entries."""
    from app.api.main import get_runtime
    runtime = get_runtime()

    entries = runtime.observability.get_audit_log(limit=limit, event=event)
    return AuditLogResponse(
        entries=[
            {
                "event": e.event,
                "layer": e.layer,
                "subject": e.subject,
                "action": e.action,
                "decision": e.decision,
                "timestamp": e.timestamp,
                "metadata": e.metadata,
            }
            for e in entries
        ],
        count=len(entries),
    )

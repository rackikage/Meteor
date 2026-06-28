"""Memory endpoint — read and write runtime memory.

Provides:
- GET /memory/{session_id} — read memory for a session
- POST /memory — write a memory entry
- GET /memory/types — list available memory types
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/memory", tags=["memory"])


class MemoryEntryRequest(BaseModel):
    memory_type: str
    content: str
    session_id: str
    metadata: dict = Field(default_factory=dict)


class MemoryEntryResponse(BaseModel):
    memory_type: str
    content: str
    session_id: str
    timestamp: str
    metadata: dict


class MemoryListResponse(BaseModel):
    entries: list[MemoryEntryResponse]
    count: int


@router.get("/types")
async def get_memory_types():
    """List available memory types."""
    return {
        "types": ["conversation", "episodic", "project", "correction"],
        "descriptions": {
            "conversation": "Chat history (role, content, session)",
            "episodic": "Events and experiences (event_type, content, session)",
            "project": "Key-value state per project (project_name, key, value)",
            "correction": "User corrections to model behavior (original, corrected, reason)",
        },
    }


@router.get("/{session_id}", response_model=MemoryListResponse)
async def get_memory(session_id: str, memory_type: Optional[str] = None) -> MemoryListResponse:
    """Read memory entries for a session."""
    from app.api.main import get_runtime
    from app.memory.contract import MemoryType

    runtime = get_runtime()

    if memory_type:
        try:
            mem_type = MemoryType(memory_type)
        except ValueError:
            return MemoryListResponse(entries=[], count=0)

        entries = runtime.memory.read(session_id, mem_type)
    else:
        entries = []
        for mem_type in MemoryType:
            entries.extend(runtime.memory.read(session_id, mem_type))

    return MemoryListResponse(
        entries=[
            MemoryEntryResponse(
                memory_type=e.memory_type.value,
                content=e.content,
                session_id=e.session_id,
                timestamp=e.timestamp,
                metadata=e.metadata,
            )
            for e in entries
        ],
        count=len(entries),
    )


@router.post("", response_model=MemoryEntryResponse)
async def write_memory(request: MemoryEntryRequest) -> MemoryEntryResponse:
    """Write a memory entry."""
    from app.api.main import get_runtime
    from app.memory.contract import MemoryEntry, MemoryType

    runtime = get_runtime()

    try:
        mem_type = MemoryType(request.memory_type)
    except ValueError:
        raise ValueError(f"Invalid memory type: {request.memory_type}")

    entry = MemoryEntry(
        memory_type=mem_type,
        content=request.content,
        session_id=request.session_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        metadata=request.metadata,
    )

    runtime.memory.write(entry)

    return MemoryEntryResponse(
        memory_type=entry.memory_type.value,
        content=entry.content,
        session_id=entry.session_id,
        timestamp=entry.timestamp,
        metadata=entry.metadata,
    )

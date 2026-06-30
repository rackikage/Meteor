"""Node coordination API — register workers, dispatch tasks, collect results."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter(tags=["nodes"])

# Controller instance — injected by app/api/main.py
_controller = None


def init_node_controller(controller) -> None:
    global _controller
    _controller = controller


def _ctrl():
    if _controller is None:
        raise HTTPException(status_code=503, detail="Node controller not initialized")
    return _controller


# ── Pydantic models ──────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    node_id: Optional[str] = None
    address: str


class HeartbeatRequest(BaseModel):
    node_id: str


class DispatchRequest(BaseModel):
    cidr: str
    ports: list[int] = [22, 80, 443, 445, 3389, 8080, 8443]
    depth: int = 1


class ResultPayload(BaseModel):
    task_id: str
    node_id: str
    cidr: str
    open_services: list[dict] = []
    hosts_found: int = 0
    completed_at: float = 0.0
    error: Optional[str] = None


# ── Endpoints ────────────────────────────────────────────────────────

@router.post("/nodes/register")
async def register_node(req: RegisterRequest):
    node_id = _ctrl().register_node(address=req.address, node_id=req.node_id)
    return {"node_id": node_id, "status": "registered"}


@router.post("/nodes/heartbeat")
async def heartbeat(req: HeartbeatRequest):
    ok = _ctrl().heartbeat(req.node_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Unknown node")
    return {"status": "ok"}


@router.get("/nodes/task")
async def claim_task(node_id: str):
    task = _ctrl().claim_task(node_id)
    if task is None:
        return {"task": None}
    return {
        "task_id": task.task_id,
        "cidr": task.cidr,
        "ports": task.ports,
        "depth": task.depth,
    }


@router.post("/nodes/result")
async def post_result(payload: ResultPayload):
    data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    ok = _ctrl().complete_task(payload.task_id, data)
    if not ok:
        raise HTTPException(status_code=404, detail="Unknown task")
    return {"status": "accepted"}


@router.post("/nodes/dispatch")
async def dispatch(req: DispatchRequest):
    task_id = _ctrl().enqueue(req.cidr, req.ports, req.depth)
    return {"task_id": task_id, "cidr": req.cidr}


@router.get("/nodes/status")
async def node_status():
    return _ctrl().status()

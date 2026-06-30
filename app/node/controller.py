"""Distributed node controller — coordinates remote Meteor worker agents.

Architecture
────────────
  Controller (this file)
    Runs inside the main Meteor instance.
    Maintains a registry of connected worker nodes.
    Distributes scan tasks to workers via HTTP.
    Collects results and merges them into the local graph.

  Worker (worker.py)
    Runs on a remote host.
    Registers itself with the controller on startup.
    Polls /api/v1/nodes/task for work.
    Posts results to /api/v1/nodes/result.

Wire the controller into FastAPI via app/api/v1/endpoints/nodes.py.

Meteor Doctrine #10: Every component must be replaceable.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class NodeInfo:
    node_id: str
    address: str          # http://host:port of the worker
    registered_at: float = field(default_factory=time.monotonic)
    last_seen: float = field(default_factory=time.monotonic)
    tasks_dispatched: int = 0
    tasks_completed: int = 0


@dataclass
class ScanTask:
    task_id: str
    cidr: str
    ports: list[int]
    depth: int = 1
    created_at: float = field(default_factory=time.monotonic)
    assigned_to: Optional[str] = None
    completed: bool = False
    result: Optional[dict] = None


class NodeController:
    """Manages worker nodes and distributes scan tasks.

    Usage (from API endpoints):
        controller = NodeController()
        node_id = controller.register_node("http://worker-host:9000")
        task_id = controller.enqueue("10.0.0.0/24", [22, 80, 443])
        await controller.dispatch_pending()
    """

    # Workers not seen in this many seconds are considered dead
    HEARTBEAT_TIMEOUT = 120.0

    def __init__(self) -> None:
        self._nodes: dict[str, NodeInfo] = {}
        self._tasks: dict[str, ScanTask] = {}
        self._task_queue: asyncio.Queue[str] = asyncio.Queue()
        self._dispatch_lock = asyncio.Lock()

    # ── Node registration ────────────────────────────────────────────

    def register_node(self, address: str, node_id: Optional[str] = None) -> str:
        node_id = node_id or str(uuid.uuid4())
        self._nodes[node_id] = NodeInfo(node_id=node_id, address=address)
        logger.info("Node registered: %s @ %s", node_id, address)
        return node_id

    def heartbeat(self, node_id: str) -> bool:
        node = self._nodes.get(node_id)
        if not node:
            return False
        node.last_seen = time.monotonic()
        return True

    def active_nodes(self) -> list[NodeInfo]:
        cutoff = time.monotonic() - self.HEARTBEAT_TIMEOUT
        return [n for n in self._nodes.values() if n.last_seen >= cutoff]

    # ── Task management ──────────────────────────────────────────────

    def enqueue(self, cidr: str, ports: list[int], depth: int = 1) -> str:
        task_id = str(uuid.uuid4())
        task = ScanTask(task_id=task_id, cidr=cidr, ports=ports, depth=depth)
        self._tasks[task_id] = task
        self._task_queue.put_nowait(task_id)
        logger.info("Task queued: %s cidr=%s ports=%d", task_id[:8], cidr, len(ports))
        return task_id

    def claim_task(self, node_id: str) -> Optional[ScanTask]:
        """Worker calls this to claim the next available task."""
        try:
            while True:
                task_id = self._task_queue.get_nowait()
                task = self._tasks.get(task_id)
                if task and not task.completed and task.assigned_to is None:
                    task.assigned_to = node_id
                    node = self._nodes.get(node_id)
                    if node:
                        node.tasks_dispatched += 1
                    logger.debug("Task %s assigned to %s", task_id[:8], node_id[:8])
                    return task
        except asyncio.QueueEmpty:
            return None

    def complete_task(self, task_id: str, result: dict) -> bool:
        task = self._tasks.get(task_id)
        if not task:
            return False
        task.completed = True
        task.result = result
        node = self._nodes.get(task.assigned_to or "")
        if node:
            node.tasks_completed += 1
        logger.info("Task %s completed by %s", task_id[:8], task.assigned_to)
        return True

    def get_task(self, task_id: str) -> Optional[ScanTask]:
        return self._tasks.get(task_id)

    # ── Status ───────────────────────────────────────────────────────

    def status(self) -> dict:
        nodes = self.active_nodes()
        pending = sum(1 for t in self._tasks.values() if not t.completed)
        done = sum(1 for t in self._tasks.values() if t.completed)
        return {
            "nodes_active": len(nodes),
            "nodes_total": len(self._nodes),
            "tasks_pending": pending,
            "tasks_completed": done,
            "nodes": [
                {
                    "node_id": n.node_id,
                    "address": n.address,
                    "tasks_dispatched": n.tasks_dispatched,
                    "tasks_completed": n.tasks_completed,
                }
                for n in nodes
            ],
        }

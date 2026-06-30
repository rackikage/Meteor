"""Distributed worker node — runs on a remote host, polls for scan tasks.

Start on any machine with Python + Meteor cloned:
    python -m app.node.worker --controller http://controller-host:8000 --port 9001

The worker:
  1. Registers with the controller on startup.
  2. Polls GET /api/v1/nodes/task to claim work.
  3. Runs the local scanner (StatelessSynScanner or connect-scan).
  4. Posts results back to POST /api/v1/nodes/result.

Meteor Doctrine #3: Adapters isolate change.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import socket
import time
import uuid
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

POLL_INTERVAL = 2.0     # seconds between task polls when idle
HEARTBEAT_INTERVAL = 30.0


class WorkerNode:
    """Connects to a Meteor controller and executes scan tasks.

    Usage:
        worker = WorkerNode(controller_url="http://10.0.0.1:8000")
        await worker.run()   # blocks; Ctrl-C to stop
    """

    def __init__(
        self,
        controller_url: str,
        listen_port: int = 9001,
        node_id: Optional[str] = None,
        timeout: float = 30.0,
    ) -> None:
        self._controller = controller_url.rstrip("/")
        self._port = listen_port
        self._node_id = node_id or str(uuid.uuid4())
        self._timeout = timeout
        self._running = False
        self._address = f"http://{self._local_ip()}:{listen_port}"

    # ── Lifecycle ────────────────────────────────────────────────────

    async def run(self) -> None:
        """Main loop: register → poll → execute → repeat."""
        self._running = True
        logger.info("Worker %s starting (controller=%s)", self._node_id[:8], self._controller)

        if not await self._register():
            logger.error("Could not register with controller — aborting")
            return

        hb_task = asyncio.create_task(self._heartbeat_loop())
        try:
            await self._poll_loop()
        finally:
            self._running = False
            hb_task.cancel()
            logger.info("Worker %s stopped", self._node_id[:8])

    async def _register(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self._controller}/api/v1/nodes/register",
                    json={"node_id": self._node_id, "address": self._address},
                )
                return resp.status_code == 200
        except Exception as e:
            logger.error("Registration failed: %s", e)
            return False

    async def _heartbeat_loop(self) -> None:
        while self._running:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    await client.post(
                        f"{self._controller}/api/v1/nodes/heartbeat",
                        json={"node_id": self._node_id},
                    )
            except Exception:
                pass

    async def _poll_loop(self) -> None:
        while self._running:
            task = await self._claim_task()
            if task:
                result = await self._execute(task)
                await self._post_result(task["task_id"], result)
            else:
                await asyncio.sleep(POLL_INTERVAL)

    # ── Task execution ───────────────────────────────────────────────

    async def _claim_task(self) -> Optional[dict]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self._controller}/api/v1/nodes/task",
                    params={"node_id": self._node_id},
                )
                if resp.status_code == 200:
                    return resp.json()
                return None
        except Exception:
            return None

    async def _execute(self, task: dict) -> dict:
        cidr = task.get("cidr", "")
        ports = task.get("ports", [22, 80, 443])
        logger.info("Executing task %s: cidr=%s ports=%d", task["task_id"][:8], cidr, len(ports))

        try:
            from app.tools.pentest.raw_scanner import HybridScanner
            scanner = HybridScanner()
            results = await scanner.scan_range(cidr, ports)

            open_services = [
                {"ip": r.ip, "port": r.port, "service": getattr(r, "service", ""),
                 "technique": getattr(r, "scan_technique", "?")}
                for r in results if getattr(r, "open", False)
            ]

            return {
                "task_id": task["task_id"],
                "node_id": self._node_id,
                "cidr": cidr,
                "open_services": open_services,
                "hosts_found": len({s["ip"] for s in open_services}),
                "completed_at": time.time(),
                "error": None,
            }
        except Exception as e:
            logger.error("Task execution error: %s", e)
            return {
                "task_id": task["task_id"],
                "node_id": self._node_id,
                "cidr": cidr,
                "open_services": [],
                "hosts_found": 0,
                "completed_at": time.time(),
                "error": str(e),
            }

    async def _post_result(self, task_id: str, result: dict) -> None:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                await client.post(
                    f"{self._controller}/api/v1/nodes/result",
                    json=result,
                )
        except Exception as e:
            logger.warning("Could not post result for task %s: %s", task_id[:8], e)

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _local_ip() -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"


def main() -> None:
    parser = argparse.ArgumentParser(description="Meteor worker node")
    parser.add_argument("--controller", required=True, help="Controller URL e.g. http://10.0.0.1:8000")
    parser.add_argument("--port", type=int, default=9001, help="Local port (for registration)")
    parser.add_argument("--node-id", default=None, help="Fixed node ID (optional)")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    worker = WorkerNode(
        controller_url=args.controller,
        listen_port=args.port,
        node_id=args.node_id,
    )
    asyncio.run(worker.run())


if __name__ == "__main__":
    main()

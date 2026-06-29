"""Inter-App Communication — Unix sockets, D-Bus, XPC."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class IPCEndpoint:
    name: str
    path: str
    type: str
    active: bool = False


@dataclass
class IPCMessage:
    source: str
    target: str
    action: str
    payload: Any = None
    id: str = ""


class IPCManager:
    def __init__(self, socket_path: Optional[str] = None) -> None:
        self._socket_path = socket_path or tempfile.mktemp(suffix=".sock", prefix="meteor-ipc-")
        self._endpoints: dict[str, IPCEndpoint] = {}
        self._handlers: dict[str, Callable] = {}
        self._server: Optional[asyncio.AbstractServer] = None
        self._platform = {"Darwin": "macos", "Linux": "linux"}.get(os.uname().sysname, "unknown")

    async def start_server(self) -> None:
        sock_path = Path(self._socket_path)
        if sock_path.exists():
            sock_path.unlink()
        self._server = await asyncio.start_unix_server(self._handle_connection, path=str(sock_path))
        os.chmod(str(sock_path), 0o777)
        self._endpoints["meteor-ipc"] = IPCEndpoint(name="meteor-ipc", path=str(sock_path), type="unix_socket", active=True)
        logger.info("IPC server started on %s", sock_path)

    async def _handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            while True:
                data = await reader.readline()
                if not data:
                    break
                try:
                    msg = json.loads(data.decode())
                    response = await self._dispatch(msg)
                    writer.write((json.dumps(response) + "\n").encode())
                    await writer.drain()
                except json.JSONDecodeError:
                    writer.write((json.dumps({"error": "invalid JSON"}) + "\n").encode())
                    await writer.drain()
        except (asyncio.CancelledError, ConnectionResetError):
            pass
        finally:
            writer.close()

    async def _dispatch(self, msg: dict) -> dict:
        action = msg.get("action", "")
        handler = self._handlers.get(action)
        if handler:
            try:
                result = handler(msg.get("payload"))
                return {"status": "ok", "result": result}
            except Exception as e:
                return {"status": "error", "error": str(e)}
        return {"status": "error", "error": f"no handler for: {action}"}

    def on(self, action: str, handler: Callable) -> None:
        self._handlers[action] = handler

    def open_in_vscode(self, file_path: str, line: int = 0) -> bool:
        try:
            cmd = ["code", "--goto", f"{file_path}:{line}"] if line else ["code", file_path]
            subprocess.run(cmd, capture_output=True, timeout=10)
            return True
        except FileNotFoundError:
            return False

    def named_pipe_write(self, pipe_path: str, data: str) -> bool:
        try:
            with open(pipe_path, "w") as f:
                f.write(data)
            return True
        except Exception as e:
            logger.error("Named pipe failed: %s", e)
            return False

    def register_endpoint(self, endpoint: IPCEndpoint) -> None:
        self._endpoints[endpoint.name] = endpoint

    def remove_endpoint(self, name: str) -> bool:
        return bool(self._endpoints.pop(name, None))

    def list_endpoints(self) -> list[dict]:
        return [{"name": n, "path": e.path, "type": e.type, "active": e.active} for n, e in self._endpoints.items()]

    async def shutdown(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        if Path(self._socket_path).exists():
            Path(self._socket_path).unlink()

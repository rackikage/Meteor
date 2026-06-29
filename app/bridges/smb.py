"""SMB Bridge — native SMB share enumeration and file access.

Uses smbclient (from Samba suite) to list shares, enumerate directories,
and extract file contents from Windows/Samba hosts.

Publishes: share.discovered, credential.found (when auth succeeds)
"""

from __future__ import annotations

import asyncio
import logging
import shutil
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

SMB_BINARY = shutil.which("smbclient")


@dataclass
class SmbShare:
    name: str
    share_type: str = "disk"
    comment: str = ""


@dataclass
class SmbResult:
    host: str
    shares: list[SmbShare] = field(default_factory=list)
    accessible: bool = False
    error: str = ""


class SmbBridge:
    """Enumerate SMB shares and access files on remote Windows/Samba hosts."""

    def __init__(self, event_bus: Optional[any] = None, timeout: float = 15.0):
        self._bus = event_bus
        self._timeout = timeout

    @property
    def available(self) -> bool:
        return SMB_BINARY is not None

    async def list_shares(self, host: str, username: str = "",
                          password: str = "", domain: str = "") -> SmbResult:
        """List all SMB shares on a host. Optionally with credentials."""
        if not self.available:
            return SmbResult(host=host, error="smbclient not installed")

        args = [SMB_BINARY, "-g", "-L", f"//{host}"]
        if username:
            args.extend(["-U", f"{domain}\\{username}" if domain else username])
        if password:
            args[-1] = f"{args[-1]}%{password}"

        try:
            proc = await asyncio.create_subprocess_exec(
                *args, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self._timeout,
            )
            output = stdout.decode("utf-8", errors="replace")

            result = SmbResult(host=host, accessible=proc.returncode == 0)
            if proc.returncode != 0:
                result.error = stderr.decode("utf-8", errors="replace")[:200]
                return result

            result.shares = self._parse_shares(output)

            for share in result.shares:
                if self._bus:
                    await self._bus.publish("share.discovered", {
                        "host": host, "name": share.name,
                        "share_type": share.share_type,
                        "source": "smb_bridge",
                    })

            return result

        except asyncio.TimeoutError:
            return SmbResult(host=host, error="Timeout")
        except Exception as exc:
            return SmbResult(host=host, error=str(exc))

    async def list_directory(self, host: str, share: str, path: str = "",
                             username: str = "", password: str = "",
                             domain: str = "") -> list[str]:
        """List files in a share directory."""
        if not self.available:
            return []

        target = f"//{host}/{share}"
        if path:
            target = f"{target}/{path}"

        args = [SMB_BINARY, "-g", "-c", "ls", target]
        if username:
            auth = f"{domain}\\{username}" if domain else username
            if password:
                auth = f"{auth}%{password}"
            args.extend(["-U", auth])

        try:
            proc = await asyncio.create_subprocess_exec(
                *args, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(
                proc.communicate(), timeout=self._timeout,
            )
            output = stdout.decode("utf-8", errors="replace")
            return [line.strip() for line in output.splitlines() if line.strip()]
        except Exception:
            return []

    @staticmethod
    def _parse_shares(output: str) -> list[SmbShare]:
        shares = []
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("Disk|"):
                parts = line.split("|")
                if len(parts) >= 2:
                    shares.append(SmbShare(
                        name=parts[1],
                        share_type="disk",
                        comment=parts[2] if len(parts) > 2 else "",
                    ))
        return shares

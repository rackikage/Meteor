"""Notification System — OS-native alerts."""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class Urgency(Enum):
    LOW = "low"
    NORMAL = "normal"
    CRITICAL = "critical"


@dataclass
class Notification:
    title: str
    message: str
    urgency: Urgency = Urgency.NORMAL
    sound: bool = False
    action_label: str = ""
    action_command: str = ""
    timestamp: str = ""
    delivered: bool = False


class NotificationService:
    def __init__(self) -> None:
        self._platform = {"Darwin": "macos", "Linux": "linux"}.get(os.uname().sysname, "terminal")
        self._history: list[Notification] = []
        self._enabled = True

    def send(self, title: str, message: str, urgency: Urgency = Urgency.NORMAL, sound: bool = False) -> bool:
        if not self._enabled:
            return False
        notif = Notification(title=title, message=message, urgency=urgency, sound=sound, timestamp=datetime.now(timezone.utc).isoformat())
        try:
            if self._platform == "macos":
                sound_cmd = 'sound name "Basso"' if sound else ""
                script = f'display notification "{notif.message}" with title "{notif.title}" {sound_cmd}'
                subprocess.run(["osascript", "-e", script], capture_output=True, timeout=10)
            elif self._platform == "linux":
                cmd = ["notify-send", "-u", urgency.value, notif.title, notif.message]
                subprocess.run(cmd, capture_output=True, timeout=10)
            else:
                print(f"\n[*] {notif.title}: {notif.message}\a")
            notif.delivered = True
            self._history.append(notif)
            return True
        except Exception as e:
            logger.warning("Notification failed: %s", e)
            print(f"\n[*] {notif.title}: {notif.message}\a")
            self._history.append(notif)
            return False

    def task_complete(self, task_name: str, duration_s: float) -> bool:
        return self.send("Task Complete", f"{task_name}\nCompleted in {duration_s:.1f}s")

    def task_failed(self, task_name: str, error: str) -> bool:
        return self.send("Task Failed", f"{task_name}\n{error}", Urgency.CRITICAL, sound=True)

    def disable(self) -> None:
        self._enabled = False

    def enable(self) -> None:
        self._enabled = True

    def get_history(self, limit: int = 20) -> list[dict]:
        return [{"title": n.title, "message": n.message[:100], "urgency": n.urgency.value, "timestamp": n.timestamp, "delivered": n.delivered} for n in self._history[-limit:]]

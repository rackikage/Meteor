"""Scheduler / Cron Integration — recurring tasks, timers, health reports."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class ScheduledTask:
    name: str
    command: str
    schedule: str
    enabled: bool = True
    last_run: Optional[str] = None
    last_status: Optional[str] = None
    run_count: int = 0
    metadata: dict = field(default_factory=dict)


class SchedulerService:
    def __init__(self) -> None:
        self._tasks: dict[str, ScheduledTask] = {}
        self._callbacks: dict[str, Callable] = {}
        self._running: dict[str, asyncio.Task] = {}
        self._persist_path = os.path.expanduser("~/.meteor/scheduler_tasks.json")
        self.load()

    def add_task(self, name: str, command: str, schedule: str, callback: Optional[Callable] = None) -> ScheduledTask:
        task = ScheduledTask(name=name, command=command, schedule=schedule)
        self._tasks[name] = task
        if callback:
            self._callbacks[name] = callback
        self._save()
        logger.info("Task added: %s (%s)", name, schedule)
        return task

    def remove_task(self, name: str) -> bool:
        if name in self._tasks:
            del self._tasks[name]
            self._callbacks.pop(name, None)
            if name in self._running:
                self._running[name].cancel()
                del self._running[name]
            self._save()
            return True
        return False

    def get_task(self, name: str) -> Optional[ScheduledTask]:
        return self._tasks.get(name)

    def list_tasks(self) -> list[dict]:
        return [{"name": t.name, "command": t.command[:100], "schedule": t.schedule, "enabled": t.enabled, "last_run": t.last_run, "last_status": t.last_status, "run_count": t.run_count} for t in self._tasks.values()]

    def enable_task(self, name: str) -> bool:
        if name in self._tasks:
            self._tasks[name].enabled = True
            self._save()
            return True
        return False

    def disable_task(self, name: str) -> bool:
        if name in self._tasks:
            self._tasks[name].enabled = False
            self._save()
            return True
        return False

    def parse_interval(self, schedule: str) -> float:
        if schedule == "daily":
            return 86400.0
        elif schedule == "hourly":
            return 3600.0
        elif schedule.startswith("interval:"):
            return float(schedule.split(":")[1])
        elif schedule == "minutely":
            return 60.0
        return 3600.0

    def install_launchd_plist(self, task: ScheduledTask) -> str:
        label = f"com.meteor.scheduler.{task.name}"
        plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
    <key>Label</key><string>{label}</string>
    <key>ProgramArguments</key><array><string>/bin/bash</string><string>-c</string><string>{task.command}</string></array>
    <key>StartInterval</key><integer>{int(self.parse_interval(task.schedule))}</integer>
    <key>RunAtLoad</key><true/>
</dict></plist>"""
        plist_path = os.path.expanduser(f"~/Library/LaunchAgents/{label}.plist")
        os.makedirs(os.path.dirname(plist_path), exist_ok=True)
        with open(plist_path, "w") as f:
            f.write(plist)
        subprocess.run(["launchctl", "load", plist_path], capture_output=True, timeout=10)
        return plist_path

    def run_once(self, command: str, delay_s: float = 0) -> asyncio.Task:
        async def _delayed():
            await asyncio.sleep(delay_s)
            from app.tools.system.shell import ShellSandbox
            return await ShellSandbox().run(command)
        return asyncio.create_task(_delayed())

    def _save(self) -> None:
        data = [{"name": t.name, "command": t.command, "schedule": t.schedule, "enabled": t.enabled, "last_run": t.last_run, "last_status": t.last_status, "run_count": t.run_count} for t in self._tasks.values()]
        os.makedirs(os.path.dirname(self._persist_path), exist_ok=True)
        with open(self._persist_path, "w") as f:
            json.dump(data, f, indent=2)

    def load(self) -> None:
        if os.path.exists(self._persist_path):
            with open(self._persist_path) as f:
                data = json.load(f)
            for item in data:
                self._tasks[item["name"]] = ScheduledTask(name=item["name"], command=item["command"], schedule=item["schedule"], enabled=item.get("enabled", True), last_run=item.get("last_run"), last_status=item.get("last_status"), run_count=item.get("run_count", 0))

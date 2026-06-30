"""Plugin contract — interface every Meteor plugin must satisfy.

A plugin is any Python module in the repo-root `plugins/` directory that
defines PLUGIN_NAME.  All hook functions are optional — implement only the
ones you need.

Hook signatures
───────────────
  scan_hook(ip, ports) → list[int]
      Called before scanning a host. May add, remove, or reorder ports.

  analyze_hook(intel: dict) → dict
      Called after a service is researched. May annotate intel with extra
      fields.  The returned dict is written to the agent report.

  report_hook(report: dict) → dict
      Called before the final AgentReport is returned. May add summary
      fields, write to external systems, etc.

Example
───────
  # plugins/my_plugin.py
  PLUGIN_NAME    = "my_plugin"
  PLUGIN_VERSION = "1.0.0"

  def scan_hook(ip: str, ports: list[int]) -> list[int]:
      return ports + [8888]   # always probe 8888

  def analyze_hook(intel: dict) -> dict:
      intel["custom_tag"] = "reviewed"
      return intel
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class MeteorPlugin(Protocol):
    """Structural protocol — a module satisfies this if it has PLUGIN_NAME."""

    PLUGIN_NAME: str

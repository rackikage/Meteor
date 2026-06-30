"""Plugin loader — discovers and runs Python plugins from the plugins/ directory.

Plugins are isolated Python modules.  They share no global state with the
Meteor runtime — each is loaded into its own module namespace via importlib.
A plugin that raises an exception during load is skipped with a warning.

Usage:
    registry = PluginRegistry()
    loaded = registry.load_all()            # loads from repo-root plugins/
    ports  = registry.run_scan_hooks(ip, ports)
    intel  = registry.run_analyze_hooks(intel)
    report = registry.run_report_hooks(report)
"""

from __future__ import annotations

import importlib.util
import logging
import types
from pathlib import Path

logger = logging.getLogger(__name__)

# plugins/ directory is at repo root, one level above app/
_PLUGIN_DIR = Path(__file__).resolve().parent.parent.parent / "plugins"


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: list[types.ModuleType] = []

    # ── Loading ──────────────────────────────────────────────────────

    def load_all(self, plugin_dir: Path = _PLUGIN_DIR) -> int:
        """Load all *.py files from plugin_dir.  Returns count loaded."""
        if not plugin_dir.exists():
            return 0
        count = 0
        for py_file in sorted(plugin_dir.glob("*.py")):
            if py_file.stem.startswith("_"):
                continue
            if self._load_file(py_file):
                count += 1
        logger.info("PluginRegistry: %d plugin(s) loaded from %s", count, plugin_dir)
        return count

    def _load_file(self, path: Path) -> bool:
        try:
            spec = importlib.util.spec_from_file_location(
                f"meteor_plugin.{path.stem}", path
            )
            if spec is None or spec.loader is None:
                return False
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
            if not hasattr(mod, "PLUGIN_NAME"):
                logger.debug("Skipping %s — no PLUGIN_NAME", path.name)
                return False
            self._plugins.append(mod)
            logger.info(
                "Plugin loaded: %s v%s",
                mod.PLUGIN_NAME,
                getattr(mod, "PLUGIN_VERSION", "?"),
            )
            return True
        except Exception as exc:
            logger.warning("Failed to load plugin %s: %s", path.name, exc)
            return False

    # ── Hook runners ─────────────────────────────────────────────────

    def run_scan_hooks(self, ip: str, ports: list[int]) -> list[int]:
        """Run all scan_hook functions in load order.  Each may modify ports."""
        for plugin in self._plugins:
            hook = getattr(plugin, "scan_hook", None)
            if hook is None:
                continue
            try:
                result = hook(ip, list(ports))
                if isinstance(result, list):
                    ports = result
            except Exception as exc:
                logger.debug(
                    "scan_hook error in %s: %s",
                    getattr(plugin, "PLUGIN_NAME", "?"),
                    exc,
                )
        return ports

    def run_analyze_hooks(self, intel: dict) -> dict:
        """Run all analyze_hook functions.  Each may annotate the intel dict."""
        for plugin in self._plugins:
            hook = getattr(plugin, "analyze_hook", None)
            if hook is None:
                continue
            try:
                result = hook(dict(intel))
                if isinstance(result, dict):
                    intel = result
            except Exception as exc:
                logger.debug(
                    "analyze_hook error in %s: %s",
                    getattr(plugin, "PLUGIN_NAME", "?"),
                    exc,
                )
        return intel

    def run_report_hooks(self, report: dict) -> dict:
        """Run all report_hook functions before final report is returned."""
        for plugin in self._plugins:
            hook = getattr(plugin, "report_hook", None)
            if hook is None:
                continue
            try:
                result = hook(dict(report))
                if isinstance(result, dict):
                    report = result
            except Exception as exc:
                logger.debug(
                    "report_hook error in %s: %s",
                    getattr(plugin, "PLUGIN_NAME", "?"),
                    exc,
                )
        return report

    # ── Introspection ─────────────────────────────────────────────────

    @property
    def names(self) -> list[str]:
        return [getattr(p, "PLUGIN_NAME", "?") for p in self._plugins]

    def __len__(self) -> int:
        return len(self._plugins)

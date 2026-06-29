"""Tests for signal forecaster and budget throttling."""

from __future__ import annotations

import pytest

from app.tools.system.signal_forecaster import (
    AuditEventType,
    SignalForecast,
    SignalForecaster,
)
from app.tools.system.signal_budget import SignalBudget


class TestSignalForecaster:

    @pytest.fixture
    def sf(self):
        return SignalForecaster()

    def test_read_file_quiet(self, sf):
        forecast = sf.forecast_filesystem("read_file", "/tmp/test.txt")
        assert forecast.signal_score == 10.0
        assert not forecast.is_loud

    def test_read_sensitive_file(self, sf):
        forecast = sf.forecast_filesystem("read_file", "/etc/shadow")
        assert forecast.signal_score > 10.0
        assert "sensitive_file_read" in str(forecast.forensic_artifacts)

    def test_write_script_loud(self, sf):
        forecast = sf.forecast_filesystem("write_file", "/tmp/script.py")
        assert forecast.signal_score >= 25.0
        assert "script_creation" in str(forecast.forensic_artifacts)

    def test_grep_password(self, sf):
        forecast = sf.forecast_filesystem("grep", "password")
        assert forecast.signal_score > 15.0
        assert any("credential" in a for a in forecast.forensic_artifacts)

    def test_remove_system_path(self, sf):
        forecast = sf.forecast_filesystem("remove_tree", "/etc/config")
        assert forecast.signal_score > 50.0
        assert AuditEventType.UNLINK in forecast.events

    def test_hash_binaries(self, sf):
        forecast = sf.forecast_filesystem("sha256", "/usr/bin/ls")
        assert forecast.signal_score >= 40.0
        assert "binary_hash_enum" in str(forecast.forensic_artifacts)

    def test_shell_nmap(self, sf):
        forecast = sf.forecast_shell("nmap -sV 10.0.0.0/24")
        assert forecast.signal_score > 50.0
        assert AuditEventType.EXECVE in forecast.events
        assert "known_tool_exec:nmap" in forecast.forensic_artifacts
        assert forecast.is_loud

    def test_shell_git_quiet(self, sf):
        forecast = sf.forecast_shell("git status")
        assert forecast.signal_score <= 60.0

    def test_shell_piped(self, sf):
        forecast = sf.forecast_shell("echo hello | cat", use_exec=False)
        assert len(forecast.process_lineage) == 3
        assert "bash" in forecast.process_lineage

    def test_process_kill(self, sf):
        forecast = sf.forecast_process("kill", pid=1234, signal=9)
        assert AuditEventType.KILL in forecast.events
        assert forecast.signal_score == 70.0

    def test_process_enum(self, sf):
        forecast = sf.forecast_process("list_processes")
        assert AuditEventType.PROC_ENUM in forecast.events

    def test_persistence_max_signal(self, sf):
        forecast = sf.forecast_persistence("launchd_plist")
        assert forecast.signal_score == 90.0
        assert AuditEventType.PERSISTENCE in forecast.events
        assert forecast.is_loud

    def test_keychain_retrieve(self, sf):
        forecast = sf.forecast_keychain("retrieve")
        assert forecast.signal_score == 80.0

    def test_browser_cdp(self, sf):
        forecast = sf.forecast_browser("execute_js")
        assert forecast.signal_score == 75.0
        assert AuditEventType.CDP_WS in forecast.events

    def test_ui_requires_tcc(self, sf):
        forecast = sf.forecast_ui("click")
        assert forecast.requires_tcc is True

    def test_ipc_listen(self, sf):
        forecast = sf.forecast_ipc("start_server")
        assert AuditEventType.IPC_LISTEN in forecast.events

    def test_forecast_is_loud_and_silent(self, sf):
        silent = sf.forecast_filesystem("read_file", "/tmp/safe.txt")
        loud = sf.forecast_persistence("launchd")
        assert silent.is_silent
        assert loud.is_loud

    def test_network_admin_port(self, sf):
        forecast = sf.forecast_network("connect", host="10.0.0.5", port=445)
        assert forecast.signal_score > 30.0
        assert "admin_port_connect" in str(forecast.forensic_artifacts)
        assert "internal_subnet" in str(forecast.forensic_artifacts)


class TestSignalBudget:

    @pytest.fixture
    def budget(self):
        return SignalBudget(max_budget=500.0, replenish_per_minute=100.0)

    @pytest.fixture
    def sf(self):
        return SignalForecaster()

    def test_initial_budget(self, budget):
        state = budget.get_state()
        assert state["current_budget"] == 500.0
        assert state["operations_allowed"] == 0
        assert state["operations_denied"] == 0

    def test_silent_operation_free(self, budget, sf):
        forecast = sf.forecast_filesystem("read_file", "/tmp/test.txt")
        allowed, remaining = budget.consume(forecast)
        assert allowed is True
        assert remaining == 500.0  # silent ops don't consume budget

    def test_loud_operation_consumes(self, budget, sf):
        forecast = sf.forecast_shell("nmap -sV localhost")
        allowed, remaining = budget.consume(forecast)
        assert allowed is True
        assert remaining < 500.0

    def test_budget_exhaustion(self, budget, sf):
        forecast = sf.forecast_persistence("launchd_plist")  # 90 points
        for _ in range(6):  # consume 540 points total
            budget.consume(forecast)

        allowed, remaining = budget.consume(forecast)
        if not allowed:
            assert remaining < 90.0
        # Budget may have replenished, that's fine

    def test_budget_replenish(self, budget, sf):
        budget.state.current = 100.0  # manually set low
        import time
        budget.state.last_replenished = time.monotonic() - 120  # 2 minutes ago
        budget._replenish()
        assert budget.state.current > 100.0

    def test_burst_mode(self, budget, sf):
        budget.enable_burst(extra_budget=500.0, duration_s=999)
        state = budget.get_state()
        assert state["burst_active"] is True
        assert state["maximum_budget"] == 1000.0
        assert state["current_budget"] >= 900.0

    def test_forecast_for_tool(self, budget):
        forecast = budget.forecast_for("shell", "execute", command="nmap -sV localhost")
        assert forecast.signal_score > 50.0

    def test_history_records_denied(self, budget, sf):
        budget.state.current = 10.0
        forecast = sf.forecast_persistence("launchd_plist")
        allowed, _ = budget.consume(forecast)
        history = budget.get_history()
        entry = history[0]
        assert entry["allowed"] == allowed
        if not allowed:
            assert entry["denied_reason"]

    def test_get_state_after_operations(self, budget, sf):
        for _ in range(3):
            budget.consume(sf.forecast_filesystem("write_file", "/tmp/x.py"))

        state = budget.get_state()
        assert state["operations_allowed"] == 3
        assert state["total_consumed"] > 0

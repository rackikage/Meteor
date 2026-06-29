"""Signal Forecaster — predict OS telemetry before execution.

Meteor Doctrine #1: Policy gates everything. Doctrine #2: Every tool emits signals.
This module bridges them — before every syscall-generating operation, it forecasts
the audit events the kernel will emit, the process tree topology it will create,
and the forensic artifacts it will leave.

This is NOT evasion. It's architectural honesty — the agent operates with full
knowledge of its own telemetry footprint and gates operations accordingly.

Design principle: treat host-level telemetry as an environmental constraint,
not as a detection vector to be evaded.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class AuditEventType(str, Enum):
    EXECVE = "execve"             # process creation / fork+exec
    OPEN = "open"                 # file open (read or write)
    CONNECT = "connect"           # network socket connect
    BIND = "bind"                 # network socket bind
    SENDTO = "sendto"             # data transmission
    SOCKET_CREATE = "socket"      # socket creation (Unix domain or TCP)
    MKDIR = "mkdir"              # directory creation
    UNLINK = "unlink"            # file/dir deletion
    KILL = "kill"                # signal to another process
    PTRACE = "ptrace"            # process tracing (not used by userland)
    KEYCHAIN_ACCESS = "keychain"  # macOS security / Linux secret-tool
    APPLESCRIPT = "osascript"    # AppleScript execution
    ACCESSIBILITY = "ax"         # Accessibility API access
    CDP_WS = "cdp_websocket"     # Chrome DevTools Protocol
    IPC_LISTEN = "ipc_listen"    # Unix domain socket listen
    FIM_WRITE = "fim_write"      # File Integrity Monitoring trigger
    PERSISTENCE = "persistence"  # launchd/systemd/cron registration
    PROC_ENUM = "proc_enum"      # Process enumeration
    HASH_READ = "hash_read"      # Reading files for hashing


@dataclass
class SignalForecast:
    """Prediction of OS-level audit events an operation will generate.

    Computed BEFORE execution so the policy engine can gate or rate-limit.
    """
    operation: str
    events: list[AuditEventType] = field(default_factory=list)
    process_lineage: list[str] = field(default_factory=list)
    syscall_count: int = 0
    file_targets: list[str] = field(default_factory=list)
    net_targets: list[str] = field(default_factory=list)
    signal_score: float = 0.0         # 0.0 = silent, 100.0 = maximum noise
    requires_tcc: bool = False
    requires_root: bool = False
    forensic_artifacts: list[str] = field(default_factory=list)

    @property
    def is_loud(self) -> bool:
        return self.signal_score >= 50.0

    @property
    def is_silent(self) -> bool:
        return self.signal_score <= 10.0


class SignalForecaster:
    """Predicts OS audit events for each tool capability.

    The forecast is computed BEFORE the operation executes, allowing the
    policy engine to:
    1. Gate the operation (deny if signal budget exceeded)
    2. Rate-limit (throttle if approaching budget threshold)
    3. Audit-log the expected signal (pre-execution audit)
    """

    # Signal score multipliers per event type
    # These are empirically derived from audit framework sensitivity:
    #   PERSISTENCE is the loudest (FIM + launchd logging + new file)
    #   OPEN read is the quietest (normal developer activity)
    EVENT_LOUDNESS: dict[AuditEventType, float] = {
        AuditEventType.PERSISTENCE:    90.0,
        AuditEventType.APPLESCRIPT:   85.0,
        AuditEventType.ACCESSIBILITY: 85.0,
        AuditEventType.KEYCHAIN_ACCESS: 80.0,
        AuditEventType.CDP_WS:        75.0,
        AuditEventType.KILL:          70.0,
        AuditEventType.PROC_ENUM:     65.0,
        AuditEventType.BIND:          60.0,
        AuditEventType.IPC_LISTEN:    55.0,
        AuditEventType.EXECVE:        50.0,
        AuditEventType.SOCKET_CREATE: 45.0,
        AuditEventType.CONNECT:       40.0,
        AuditEventType.SENDTO:        35.0,
        AuditEventType.UNLINK:        30.0,
        AuditEventType.MKDIR:         25.0,
        AuditEventType.FIM_WRITE:     20.0,
        AuditEventType.HASH_READ:     15.0,
        AuditEventType.OPEN:          10.0,
    }

    def forecast_filesystem(self, operation: str, path: str = "") -> SignalForecast:
        """Forecast signals for filesystem operations."""
        forecast = SignalForecast(
            operation=f"filesystem.{operation}",
            file_targets=[path] if path else [],
        )

        if operation == "read_file":
            forecast.events = [AuditEventType.OPEN]
            forecast.signal_score = self.EVENT_LOUDNESS[AuditEventType.OPEN]
            if "/etc/" in path or "/var/log/" in path or path.endswith("/shadow"):
                forecast.signal_score += 30.0
                forecast.forensic_artifacts.append(f"sensitive_file_read:{path}")

        elif operation == "write_file":
            forecast.events = [AuditEventType.OPEN, AuditEventType.FIM_WRITE]
            forecast.signal_score = 25.0
            if path.endswith((".py", ".sh", ".plist", ".service", ".timer")):
                forecast.signal_score += 25.0
                forecast.forensic_artifacts.append(f"script_creation:{path}")
            if "/etc/" in path or "/Library/" in path:
                forecast.signal_score += 40.0

        elif operation == "grep":
            forecast.signal_score = 15.0
            if "password" in path.lower() or "secret" in path.lower():
                forecast.signal_score += 30.0
                forecast.forensic_artifacts.append(f"credential_search:{path}")

        elif operation in ("remove", "remove_tree"):
            forecast.events = [AuditEventType.UNLINK]
            forecast.signal_score = self.EVENT_LOUDNESS[AuditEventType.UNLINK]
            if path.startswith("/etc") or path.startswith("/var"):
                forecast.signal_score += 50.0

        elif operation in ("md5", "sha256"):
            forecast.events = [AuditEventType.HASH_READ]
            forecast.signal_score = self.EVENT_LOUDNESS[AuditEventType.HASH_READ]
            if "/usr/bin/" in path or "/usr/sbin/" in path:
                forecast.signal_score += 25.0
                forecast.forensic_artifacts.append(f"binary_hash_enum:{path}")

        elif operation == "which":
            forecast.signal_score = 10.0
            forecast.forensic_artifacts.append(f"executable_discovery")

        elif operation == "list_dir":
            forecast.signal_score = 5.0

        return forecast

    def forecast_shell(self, command: str, use_exec: bool = True) -> SignalForecast:
        """Forecast signals for shell command execution."""
        forecast = SignalForecast(
            operation=f"shell:{command[:80]}",
        )

        cmd_words = command.split()
        first_word = os.path.basename(cmd_words[0]) if cmd_words else command

        forecast.events = [AuditEventType.EXECVE]
        forecast.process_lineage = ["python3", first_word]
        forecast.signal_score = self.EVENT_LOUDNESS[AuditEventType.EXECVE]

        if not use_exec:
            forecast.process_lineage = ["python3", "bash", first_word]
            forecast.signal_score += 15.0

        loud_commands = {
            "nmap": 50.0, "hydra": 55.0, "crackmapexec": 55.0,
            "chisel": 45.0, "socat": 40.0, "nc": 35.0,
            "ssh": 30.0, "curl": 25.0, "wget": 25.0,
            "git": 10.0, "make": 10.0, "python3": 10.0, "pip": 10.0,
        }
        for cmd, bonus in loud_commands.items():
            if cmd in first_word:
                forecast.signal_score += bonus
                forecast.forensic_artifacts.append(f"known_tool_exec:{cmd}")

        if any(x in command for x in ["-sV", "-sC", "-A", "--script"]):
            forecast.signal_score += 30.0

        return forecast

    def forecast_process(self, operation: str, pid: int = 0, signal: int = 0) -> SignalForecast:
        """Forecast signals for process management operations."""
        forecast = SignalForecast(operation=f"process.{operation}")

        if operation in ("list_processes", "find_pids", "get_process"):
            forecast.events = [AuditEventType.PROC_ENUM]
            forecast.signal_score = self.EVENT_LOUDNESS[AuditEventType.PROC_ENUM]

        elif operation == "kill":
            forecast.events = [AuditEventType.KILL, AuditEventType.PROC_ENUM]
            forecast.signal_score = self.EVENT_LOUDNESS[AuditEventType.KILL]
            forecast.forensic_artifacts.append(f"signal:{signal}_to_pid:{pid}")

        return forecast

    def forecast_network(self, operation: str, host: str = "", port: int = 0) -> SignalForecast:
        """Forecast signals for network operations."""
        forecast = SignalForecast(
            operation=f"network.{operation}",
            net_targets=[f"{host}:{port}"] if host else [],
        )

        forecast.events = [AuditEventType.SOCKET_CREATE, AuditEventType.CONNECT]
        forecast.signal_score = 45.0

        if port in (22, 445, 3389, 5985, 5986):
            forecast.signal_score += 25.0
            forecast.forensic_artifacts.append(f"admin_port_connect:{port}")

        if host.startswith(("10.", "172.", "192.168.")):
            forecast.signal_score += 15.0
            forecast.forensic_artifacts.append(f"internal_subnet:{host}")

        return forecast

    def forecast_persistence(self, method: str) -> SignalForecast:
        """Forecast signals for persistence installation."""
        forecast = SignalForecast(
            operation=f"persistence.{method}",
            events=[
                AuditEventType.PERSISTENCE,
                AuditEventType.FIM_WRITE,
                AuditEventType.OPEN,
            ],
            signal_score=self.EVENT_LOUDNESS[AuditEventType.PERSISTENCE],
            forensic_artifacts=[
                f"persistence_method:{method}",
                f"launchd_plist_written" if "launchd" in method else "",
                f"systemd_timer_written" if "systemd" in method else "",
            ],
        )
        return forecast

    def forecast_keychain(self, operation: str) -> SignalForecast:
        """Forecast signals for keychain/credential operations."""
        forecast = SignalForecast(operation=f"keychain.{operation}")
        if operation == "retrieve":
            forecast.events = [AuditEventType.KEYCHAIN_ACCESS]
            forecast.signal_score = self.EVENT_LOUDNESS[AuditEventType.KEYCHAIN_ACCESS]
        elif operation == "store":
            forecast.events = [AuditEventType.KEYCHAIN_ACCESS]
            forecast.signal_score = self.EVENT_LOUDNESS[AuditEventType.KEYCHAIN_ACCESS] - 10.0
        return forecast

    def forecast_browser(self, operation: str) -> SignalForecast:
        """Forecast signals for browser/CDP operations."""
        forecast = SignalForecast(operation=f"browser.{operation}")
        forecast.events = [AuditEventType.CDP_WS, AuditEventType.SOCKET_CREATE, AuditEventType.CONNECT]
        forecast.signal_score = self.EVENT_LOUDNESS[AuditEventType.CDP_WS]
        forecast.forensic_artifacts.append("cdp_connection:localhost:9222")
        return forecast

    def forecast_ui(self, operation: str) -> SignalForecast:
        """Forecast signals for UI automation operations."""
        forecast = SignalForecast(operation=f"ui.{operation}")
        forecast.events = [AuditEventType.APPLESCRIPT, AuditEventType.ACCESSIBILITY]
        forecast.signal_score = self.EVENT_LOUDNESS[AuditEventType.APPLESCRIPT]
        forecast.requires_tcc = True
        forecast.forensic_artifacts.append("accessibility_api_access")
        return forecast

    def forecast_ipc(self, operation: str) -> SignalForecast:
        """Forecast signals for IPC operations."""
        forecast = SignalForecast(operation=f"ipc.{operation}")
        forecast.events = [AuditEventType.SOCKET_CREATE, AuditEventType.IPC_LISTEN, AuditEventType.BIND]
        forecast.signal_score = self.EVENT_LOUDNESS[AuditEventType.IPC_LISTEN]
        forecast.forensic_artifacts.append("unix_socket:/tmp/meteor-ipc-*.sock")
        return forecast

"""System tools — OS-level integration for Meteor.

Gives the runtime hands, eyes, and a voice into the host operating system:
1. Filesystem Agent   - Read, write, glob, grep files
2. Shell Execution    - Run bash/zsh commands in a sandbox
3. Process Manager    - Monitor, restart, list processes
4. UI Automation      - AppleScript/Accessibility API interaction
5. Clipboard          - System clipboard read/write
6. Notifications      - OS-native alerts (macOS/Linux)
7. Browser Bridge     - Live browser tab reading/navigation
8. Keychain           - Secure credential storage
9. Scheduler          - Cron/launchd/systemd recurring tasks
10. IPC               - Unix sockets, D-Bus inter-app communication

Meteor Doctrine #2: Every tool is policy-gated.
"""

from app.tools.system.registry import SystemToolRegistry, ToolAccess, ToolCapability
from app.tools.system.filesystem import FilesystemAgent
from app.tools.system.shell import ShellSandbox, ShellConfig
from app.tools.system.process import ProcessManager
from app.tools.system.ui_automation import UIAutomation
from app.tools.system.clipboard import ClipboardManager
from app.tools.system.notifications import NotificationService, Urgency
from app.tools.system.browser_bridge import BrowserBridge
from app.tools.system.keychain import KeychainManager
from app.tools.system.scheduler import SchedulerService
from app.tools.system.ipc import IPCManager

__all__ = [
    "SystemToolRegistry",
    "ToolAccess",
    "ToolCapability",
    "FilesystemAgent",
    "ShellSandbox",
    "ShellConfig",
    "ProcessManager",
    "UIAutomation",
    "ClipboardManager",
    "NotificationService",
    "Urgency",
    "BrowserBridge",
    "KeychainManager",
    "SchedulerService",
    "IPCManager",
]

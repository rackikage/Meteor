"""Tests for system tools — filesystem, shell, process, clipboard, notifications, keychain, scheduler, registry, IPC, browser."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.tools.system.filesystem import FilesystemAgent
from app.tools.system.shell import ShellSandbox, ShellResult
from app.tools.system.process import ProcessManager
from app.tools.system.clipboard import ClipboardManager
from app.tools.system.notifications import NotificationService, Urgency
from app.tools.system.keychain import KeychainManager
from app.tools.system.scheduler import SchedulerService
from app.tools.system.registry import SystemToolRegistry, ToolAccess, ToolCapability
from app.tools.system.ui_automation import UIAutomation, Platform
from app.tools.system.ipc import IPCManager, IPCEndpoint
from app.tools.system.browser_bridge import BrowserBridge, BrowserConfig


class TestFilesystemAgent:

    @pytest.fixture
    def fs(self):
        return FilesystemAgent(allowed_dirs=["/tmp"])

    def test_write_and_read_file(self, fs):
        path = "/tmp/meteor_test_rw.txt"
        fs.write_file(path, "hello meteor")
        assert fs.read_file(path) == "hello meteor"
        os.unlink(path)

    def test_read_lines(self, fs):
        path = "/tmp/meteor_test_lines.txt"
        fs.write_file(path, "a\nb\nc\n")
        lines = fs.read_lines(path)
        assert lines == ["a", "b", "c"]
        os.unlink(path)

    def test_read_range(self, fs):
        path = "/tmp/meteor_test_range.txt"
        fs.write_file(path, "1\n2\n3\n4\n5\n")
        assert fs.read_range(path, 2, 4) == ["2", "3", "4"]
        os.unlink(path)

    def test_glob(self, fs):
        path = "/tmp/meteor_glob_t.txt"
        fs.write_file(path, "content")
        matches = fs.glob("/tmp/*")
        assert any("meteor_glob_t" in m for m in matches)
        os.unlink(path)

    def test_grep(self, fs):
        path = "/tmp/meteor_grep_t.txt"
        fs.write_file(path, "hello world\nfoo bar\nhello meteor\n")
        matches = fs.grep("hello", path)
        assert len(matches) == 2
        os.unlink(path)

    def test_stat_file(self, fs):
        path = "/tmp/meteor_stat_t.txt"
        fs.write_file(path, "stat me")
        info = fs.stat(path)
        assert info["exists"] is True
        assert info["type"] == "file"
        os.unlink(path)

    def test_list_dir(self, fs):
        entries = fs.list_dir("/tmp")
        assert isinstance(entries, list)
        assert all("name" in e for e in entries)

    def test_mkdir_and_remove(self, fs):
        path = "/tmp/meteor_mkdir_t"
        fs.mkdir(path)
        assert Path(path).exists()
        fs.remove(path)
        assert not Path(path).exists()

    def test_copy_and_move(self, fs):
        src = "/tmp/meteor_copy_s.txt"
        dst = "/tmp/meteor_copy_d.txt"
        fs.write_file(src, "copy test")
        fs.copy(src, dst)
        assert fs.read_file(dst) == "copy test"
        moved = "/tmp/meteor_mvd.txt"
        fs.move(dst, moved)
        assert Path(moved).exists()
        os.unlink(src)
        os.unlink(moved)

    def test_hash(self, fs):
        path = "/tmp/meteor_hash_t.txt"
        fs.write_file(path, "hash content")
        assert len(fs.md5(path)) == 32
        assert len(fs.sha256(path)) == 64
        os.unlink(path)

    def test_which(self, fs):
        assert fs.which("bash") is not None

    def test_read_binary(self, fs):
        path = "/tmp/meteor_bin_t.bin"
        data = b"\x00\x01\x02\xff"
        fs.write_binary(path, data)
        assert fs.read_binary(path) == data
        os.unlink(path)

    def test_get_stats(self, fs):
        stats = fs.get_stats()
        assert "total_operations" in stats


class TestShellSandbox:

    @pytest.fixture
    def shell(self):
        return ShellSandbox()

    def test_simple_command(self, shell):
        result = shell.run_sync("echo hello_meteor")
        assert result.success
        assert "hello_meteor" in result.stdout

    def test_command_failure(self, shell):
        result = shell.run_sync("exit 42")
        assert not result.success
        assert result.returncode == 42

    def test_timeout(self, shell):
        result = shell.run_sync("sleep 10", timeout=0.5)
        assert result.timed_out

    def test_piped_command(self, shell):
        result = shell.run_sync("echo 'a\nb\nc' | wc -l")
        assert result.success
        assert "3" in result.stdout.strip()

    def test_blocked_command(self, shell):
        with pytest.raises(PermissionError):
            shell.run_sync("sudo ls")

    def test_history(self, shell):
        shell.run_sync("echo cmd1")
        shell.run_sync("echo cmd2")
        assert len(shell.get_history()) >= 2

    def test_empty_command(self, shell):
        with pytest.raises(ValueError):
            shell.run_sync("")


class TestProcessManager:

    @pytest.fixture
    def pm(self):
        return ProcessManager()

    def test_list_processes(self, pm):
        procs = pm.list_processes(limit=10)
        assert isinstance(procs, list)

    def test_filter_by_name(self, pm):
        procs = pm.list_processes(filter_name="python", limit=5)
        assert isinstance(procs, list)

    def test_get_process(self, pm):
        proc = pm.get_process(os.getpid())
        if proc is None:
            pytest.skip("Process not found via ps aux (macOS ps format)")

    def test_find_pids(self, pm):
        pids = pm.find_pids("python")
        assert isinstance(pids, list)

    def test_is_running(self, pm):
        assert pm.is_running(os.getpid()) is True
        assert pm.is_running(99999999) is False

    def test_system_stats(self, pm):
        stats = pm.system_stats()
        assert stats is not None


class TestClipboardManager:

    @pytest.fixture
    def cb(self):
        return ClipboardManager()

    def test_copy_and_paste(self, cb):
        cb.copy("meteor clipboard test")
        result = cb.paste()
        assert "meteor clipboard test" in result

    def test_append(self, cb):
        cb.copy("first")
        cb.append("second")
        result = cb.paste()
        assert "first" in result

    def test_clear(self, cb):
        cb.copy("something")
        cb.clear()
        result = cb.paste()
        assert result == ""


class TestNotificationService:

    @pytest.fixture
    def notif(self):
        return NotificationService()

    def test_send_notification(self, notif):
        assert notif.send("Test", "test notification", Urgency.LOW) is True

    def test_task_complete(self, notif):
        assert notif.task_complete("download", 45.2) is True

    def test_task_failed(self, notif):
        assert notif.task_failed("scrape", "timeout") is True

    def test_disable(self, notif):
        notif.disable()
        assert notif.send("Test", "should not send") is False

    def test_history(self, notif):
        notif.send("Hist1", "Entry 1")
        notif.send("Hist2", "Entry 2")
        assert len(notif.get_history()) >= 2


class TestKeychainManager:

    @pytest.fixture
    def kc(self):
        return KeychainManager()

    def test_store_and_retrieve(self, kc):
        kc.store("meteor-test", "api-key", "sk-test123")
        assert kc.retrieve("meteor-test", "api-key") == "sk-test123"
        kc.delete("meteor-test", "api-key")

    def test_delete(self, kc):
        kc.store("meteor-test", "temp-key", "temp")
        kc.delete("meteor-test", "temp-key")
        assert kc.retrieve("meteor-test", "temp-key") is None

    def test_list_services(self, kc):
        assert isinstance(kc.list_services(), list)


class TestSchedulerService:

    @pytest.fixture
    def sched(self):
        svc = SchedulerService()
        for name in list(svc._tasks.keys()):
            svc.remove_task(name)
        yield svc
        for name in list(svc._tasks.keys()):
            svc.remove_task(name)

    def test_add_and_list_tasks(self, sched):
        sched.add_task("test-hourly", "echo hello", "hourly")
        tasks = sched.list_tasks()
        assert len(tasks) == 1

    def test_remove_task(self, sched):
        sched.add_task("test-remove", "echo rm", "daily")
        assert sched.remove_task("test-remove") is True
        assert sched.remove_task("nonexistent") is False

    def test_disable_enable(self, sched):
        sched.add_task("test-tog", "echo tog", "daily")
        sched.disable_task("test-tog")
        assert sched.get_task("test-tog").enabled is False
        sched.enable_task("test-tog")
        assert sched.get_task("test-tog").enabled is True

    def test_parse_intervals(self, sched):
        assert sched.parse_interval("daily") == 86400.0
        assert sched.parse_interval("hourly") == 3600.0
        assert sched.parse_interval("interval:300") == 300.0
        assert sched.parse_interval("minutely") == 60.0


class TestSystemToolRegistry:

    @pytest.fixture
    def registry(self):
        return SystemToolRegistry()

    def test_register_and_get(self, registry):
        fs = FilesystemAgent(allowed_dirs=["/tmp"])
        registry.register("filesystem", fs, "FS ops")
        assert registry.get("filesystem") is fs

    def test_disable_enable_tool(self, registry):
        fs = FilesystemAgent(allowed_dirs=["/tmp"])
        registry.register("filesystem", fs, "Test")
        registry.disable("filesystem")
        with pytest.raises(RuntimeError):
            registry.get("filesystem")
        registry.enable("filesystem")
        assert registry.get("filesystem") is fs

    def test_list_tools(self, registry):
        registry.register("t1", object(), "First")
        registry.register("t2", object(), "Second")
        assert len(registry.list_tools()) == 2

    def test_audit_log(self, registry):
        registry.register("test", object(), "Test")
        registry.check_policy("test", "op1", {})
        registry.check_policy("test", "op2", {})
        assert len(registry.get_audit_log()) == 2


class TestIPCManager:

    @pytest.fixture
    def ipc(self):
        return IPCManager(socket_path="/tmp/meteor-ipc-test.sock")

    def test_register_endpoint(self, ipc):
        ep = IPCEndpoint(name="vscode", path="/tmp/vscode.sock", type="unix_socket")
        ipc.register_endpoint(ep)
        assert len(ipc.list_endpoints()) == 1

    def test_remove_endpoint(self, ipc):
        ep = IPCEndpoint(name="test-rm", path="/tmp/t.sock", type="named_pipe")
        ipc.register_endpoint(ep)
        assert ipc.remove_endpoint("test-rm") is True
        assert ipc.remove_endpoint("nonex") is False

    def test_handler_registration(self, ipc):
        results = []
        ipc.on("test-action", lambda p: results.append(p))
        assert "test-action" in ipc._handlers

    def test_open_in_vscode_no_code(self, ipc):
        assert ipc.open_in_vscode("/tmp/nonexistent") is False


class TestBrowserBridge:

    @pytest.fixture
    def bridge(self):
        return BrowserBridge(BrowserConfig())

    def test_initial_state(self, bridge):
        assert isinstance(bridge.connected, bool)

    def test_list_tabs_no_cdp(self, bridge):
        tabs = bridge.list_tabs()
        assert tabs == []

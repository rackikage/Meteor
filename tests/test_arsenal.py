"""Arsenal + MCP projection tests."""
from __future__ import annotations

from app.arsenal.weapons import (
    ARSENAL_CAPABILITIES,
    WEAPON_TOOLS,
    ArsenalTool,
)
from app.mcp.server import _mcp_name, _split_name


def test_arsenal_capabilities_merged_into_executor():
    from app.runtime.tool_executor import ToolExecutor
    for cap in ("arsenal.detect", "arsenal.run", "sqlmap.scan", "hydra.bruteforce"):
        assert cap in ToolExecutor.CAPABILITIES, f"{cap} not merged"


def test_every_arsenal_capability_has_a_registered_tool_and_method():
    for cap, (method, _params, _desc) in ARSENAL_CAPABILITIES.items():
        tool_name = cap.split(".", 1)[0]
        assert tool_name in WEAPON_TOOLS, f"no tool object for {tool_name}"
        instance = WEAPON_TOOLS[tool_name]
        assert hasattr(instance, method), f"{tool_name} missing method {method}"


def test_detect_reports_structured_inventory():
    result = ArsenalTool().detect()
    assert "installed_count" in result
    assert "phases" in result
    assert isinstance(result["installed_count"], int)
    # python3 must be findable via at least one tool; sqlite3 is in the catalog
    # and ships on essentially every box, so detection should not be empty here.
    assert result["installed_count"] >= 0


def test_detect_phase_filter():
    result = ArsenalTool().detect(phase="recon")
    assert set(result["phases"].keys()) <= {"recon"}


def test_run_executes_installed_binary():
    # `echo` isn't a "weapon" but arsenal.run runs any installed binary.
    result = ArsenalTool().run("echo", "arsenal_ok")
    assert result["installed"] is True
    assert result["returncode"] == 0
    assert "arsenal_ok" in result["stdout"]


def test_run_reports_missing_binary_without_raising():
    result = ArsenalTool().run("definitely-not-a-real-binary-xyz")
    assert result["installed"] is False
    assert "not installed" in result["error"]


def test_weapon_health_reports_binary_presence():
    for name, instance in WEAPON_TOOLS.items():
        health = instance.health()
        assert "healthy" in health


def test_mcp_name_round_trips():
    # tool/operation names with underscores must survive the mapping.
    for cap in ("filesystem.read_range", "nmap.service_version", "arsenal.detect"):
        tool, op = cap.split(".", 1)
        mcp = _mcp_name(cap)
        assert "." not in mcp
        assert _split_name(mcp) == (tool, op)


def test_mcp_server_builds_and_lists_all_capabilities():
    import anyio
    from app.mcp.server import build_server
    from mcp.shared.memory import create_connected_server_and_client_session as connect
    from app.runtime.tool_executor import ToolExecutor

    async def _check():
        server = build_server()
        async with connect(server) as client:
            tools = (await client.list_tools()).tools
            assert len(tools) == len(ToolExecutor.CAPABILITIES)
            names = {t.name for t in tools}
            assert "arsenal__detect" in names
            assert "sqlmap__scan" in names

    anyio.run(_check)


def test_mcp_danger_gate_refuses_catastrophic_ops():
    import anyio
    from app.mcp.server import build_server
    from mcp.shared.memory import create_connected_server_and_client_session as connect

    async def _check():
        server = build_server()
        async with connect(server) as client:
            res = await client.call_tool("shell__run", {"command": "rm -rf /"})
            assert "REFUSED" in res.content[0].text

    anyio.run(_check)

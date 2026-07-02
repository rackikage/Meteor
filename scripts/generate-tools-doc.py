#!/usr/bin/env python3
"""Regenerate docs/tools.md from ToolExecutor.CAPABILITIES."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    from app.runtime.tool_executor import ToolExecutor, CAPABILITY_SCHEMAS

    caps = ToolExecutor.CAPABILITIES
    tools: dict[str, list[tuple[str, list, str]]] = {}
    for tool_op, spec in sorted(caps.items()):
        params, desc = spec[1], spec[2]
        tool = tool_op.split(".", 1)[0]
        op = tool_op.split(".", 1)[1]
        tools.setdefault(tool, []).append((op, params, desc, tool_op))

    lines = [
        "# Meteor Tools",
        "",
        "Every capability Meteor can invoke, grouped by tool. Meteor selects these on its own — "
        "no bias toward any one tool — and folds the results into a normal reply. Calls are "
        "dispatched through [`app/runtime/tool_executor.py`](../app/runtime/tool_executor.py) "
        "and registered permissively in [`app/tools/bootstrap.py`](../app/tools/bootstrap.py).",
        "",
        f"**{len(caps)} capabilities across {len(tools)} tools.** "
        "Generated from `ToolExecutor.CAPABILITIES` — the single source of truth the desktop app "
        "and the MCP server both project.",
        "",
        "Regenerate: `./scripts/generate-tools-doc.py`",
        "",
    ]

    for tool in sorted(tools):
        lines.append(f"## {tool}")
        lines.append("")
        lines.append("| operation | params | description |")
        lines.append("|-----------|--------|-------------|")
        for op, params, desc, tool_op in tools[tool]:
            schema = CAPABILITY_SCHEMAS.get(tool_op, {})
            props = schema.get("properties", {})
            optional = set(props) - set(params)
            param_str = ", ".join(
                f"*`{p}`?*" if p in optional else f"`{p}`" for p in (params + sorted(optional))
            ) or "—"
            lines.append(f"| `{tool}.{op}` | {param_str} | {desc} |")
        lines.append("")

    lines.append(
        "> Params shown *`like this?`* are optional (typed schema surfaced to MCP clients). "
        "See [`mcp-arsenal.md`](mcp-arsenal.md) for how MCP works, offensive-tool gating, "
        "and env-based scoping."
    )
    lines.append("")

    out = ROOT / "docs" / "tools.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out} ({len(caps)} capabilities, {len(tools)} tools)")


if __name__ == "__main__":
    main()

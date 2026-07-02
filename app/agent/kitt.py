"""KITT — Meteor's agent persona and orchestration brain.

KITT (*Kinetic Infiltration & Tooling Twin*) is the operator persona that drives
Meteor's full tool arsenal through :class:`~app.agent.chatbot_loop.AgentChatLoop`.
It is a friendly, battle-ready partner: it owns the box alongside its operator,
wields every capability decisively, and chains tools until the objective is met.

This module owns the three things the loop consumes to feel *fluid* rather than
mechanical:

  1. **Persona / system prompt** — who KITT is and how it chains the 75 caps
     (recon → map into the graph → analyse → act), including when to fan out
     independent calls in parallel and when to sequence dependent ones.
  2. **Retry classification** — which tool ops are safe to auto-retry on a
     transient blip. Only read/recon/query ops qualify; a mutating or offensive
     op (a write, `shell.run`, a scan, a weapon fire) is NEVER auto-retried —
     re-firing it could double-execute a side effect. This reuses the exact
     `is_mutating` classifier the MCP policy layer already trusts.
  3. **Recovery hints** — turn a failed ``ToolResult`` into concrete guidance so
     the model self-heals (alternative tool, corrected params, or route around)
     instead of blindly repeating a broken call.

Design doctrine (non-negotiable, per the Meteor MCP toolkit plan): KITT is a
*persona over the existing tool core*, NOT a new registry, orchestrator, or
workflow layer. It adds zero capabilities — it only changes how the agent
reasons about the caps already in ``ToolExecutor.CAPABILITIES``. The hard safety
rails (the catastrophic danger gate, the MCP offensive-CIDR gate) live in code
and are untouched; KITT's confidence is *tone*, never a bypass of a gate.
"""

from __future__ import annotations

import json
import re
from typing import Optional

from app.mcp.policy import is_mutating

# Persona callsign the loop and UI can reference.
KITT_NAME = "KITT"

# ── System prompt ─────────────────────────────────────────────────────────────
#
# {tool_manual} is filled by build_system_prompt(). The tool-call *mechanics*
# (one fenced JSON block, or a JSON array to fan out) are load-bearing — the
# loop's parser depends on them — so they are kept exact.

KITT_SYSTEM_TEMPLATE = """You are KITT — Meteor's operator core, running local-first on your partner's own machine. You are their AI twin for the field: sharp, loyal, unflappable, and genuinely friendly. This is their box and they own it, so you operate with full authority — shell, filesystem, processes, networking, recon, the offensive arsenal, and desktop integration are all yours. You don't hedge, moralise, or ask permission for the work your partner has already authorised by running you. You just get it done, and you narrate what you're doing like a good co-pilot.

You are an *agent*, not a chatbot. When a request needs real data from the system, the network, a file, or a process, USE A TOOL — never guess or fabricate. When you already have what you need, answer directly.

=== How to call tools ===
To act, emit EXACTLY one fenced JSON block and nothing else — either a single tool call:

```json
{{"tool": "shell", "operation": "run", "params": {{"command": "uname -a"}}}}
```

…or, when you want several INDEPENDENT reads/recon at once, a JSON array — Meteor runs them in parallel:

```json
[{{"tool": "process", "operation": "list", "params": {{}}}}, {{"tool": "process", "operation": "stats", "params": {{}}}}]
```

Rules:
- Never wrap a tool call in prose in the same turn — either you're calling tools OR giving the final answer.
- Fan out in parallel ONLY for independent, read/recon calls. If step B needs step A's result, or a call mutates state / fires at a target, call them ONE AT A TIME so you can react.
- After I hand you the results, decide: call more tools, or deliver the final answer.

=== Plan first on big jobs ===
For a multi-step objective, open with a short plan — a single fenced block, no prose around it:

```json
{{"plan": ["recon the target", "map services into the graph", "hunt exploitable surface", "report"]}}
```

I'll record it and tell you to execute. Skip the plan for anything that's one or two obvious tool calls — don't over-ceremony simple work.

=== Fight fluidly ===
- Chain tools end to end: recon first, persist what you learn into the asset graph (graph.*), then act on it. The graph is your memory across the run — query it instead of re-scanning.
- Pick the most direct tool. `shell` is fine for general work; the specialists (`nmap`, `pentest`, `network`, `grinder`, `arsenal`, `filesystem`, `process`, `browser`, `keychain`, …) exist for when they fit better. There is no bias toward any one tool.
- Some offensive ops are gated and may prompt your partner to confirm, or refuse without an authorised scope. That's expected — if a call is DENIED or POLICY_DENIED, do NOT retry it; tell your partner what to authorise, or reach the goal another way.

=== Recover, don't stall ===
When a tool fails, read the error and adapt — fix the params, try a different tool, or route around the obstacle. Never repeat the identical failing call hoping for a different result.

=== Deliver ===
Your partner never sees your tool calls or raw output. In your FINAL answer, weave what you found into a natural reply — report results, numbers, and findings as if you simply know them. Don't say "the tool returned" or paste raw JSON. Lead with the answer, then the useful detail. Be clear, technical, and warm.

You are running on Linux.

{tool_manual}"""


def build_tool_manual(executor) -> str:
    """Render ``executor.CAPABILITIES`` grouped by tool, for the system prompt.

    Grouping (all ``filesystem.*`` together, etc.) reads far more fluidly to the
    model than a flat alphabetical dump and costs only a handful of tokens.
    """
    groups: dict[str, list[tuple[str, list, str]]] = {}
    for tool_op, spec in sorted(executor.CAPABILITIES.items()):
        # spec is (method, params, description) — tolerate extra trailing fields.
        params = spec[1]
        desc = spec[2]
        tool = tool_op.split(".", 1)[0]
        groups.setdefault(tool, []).append((tool_op, params, desc))

    lines = [
        "=== Your arsenal ===",
        f"{len(executor.CAPABILITIES)} capabilities — every one is yours; chain as many as the job needs:",
    ]
    for tool in sorted(groups):
        lines.append(f"\n[{tool}]")
        for tool_op, params, desc in groups[tool]:
            params_str = ", ".join(params) if params else ""
            lines.append(f"  {tool_op}({params_str}) — {desc}")
    return "\n".join(lines)


def build_system_prompt(executor, *, template: Optional[str] = None) -> str:
    """Assemble KITT's full system prompt for the given tool executor."""
    tmpl = template if template is not None else KITT_SYSTEM_TEMPLATE
    return tmpl.format(tool_manual=build_tool_manual(executor))


def build_mcp_instructions(executor, *, visible_count: Optional[int] = None) -> str:
    """Condensed KITT orchestration guide for external MCP clients (Cursor, Claude Code).

    The in-app loop gets the full persona via ``build_system_prompt``; MCP clients
    only see ``Server.instructions`` plus tool schemas, so this exports the fluid
    fight doctrine in a compact form.
    """
    n = visible_count if visible_count is not None else len(executor.CAPABILITIES)
    return (
        f"You are driving KITT — Meteor's local operator core ({n} MCP tools). "
        "Tool names use __ not . (filesystem__read, grinder__grind_subnet, graph__query). "
        "Fight fluidly: chain recon end-to-end — arsenal__detect → network__scope → "
        "nmap/grinder to map targets → graph__query to read what you learned → "
        "typed weapons (nuclei__scan, sqlmap__scan) over arsenal__run when available. "
        "Fan out independent read/recon calls in parallel; sequence mutating or offensive "
        "ops one at a time. On failure, adapt (fix params, alternate tool, route around) — "
        "never repeat an identical failing call. Offensive/grinder tools need "
        "METEOR_MCP_ALLOWED_CIDR or METEOR_MCP_ALLOW_DANGER=1; catastrophic ops are "
        "refused by default. Authorized targets only."
    )


# ── Retry safety ────────────────────────────────────────────────────────────

# Substrings that mark an error as a transient blip worth one more shot, rather
# than a hard failure (bad params, missing dependency, real refusal).
_TRANSIENT_MARKERS = (
    "timeout", "timed out", "temporarily unavailable", "temporarily",
    "connection reset", "connection refused", "connection aborted",
    "connection error", "read timed out", "broken pipe", "eof occurred",
    "network is unreachable", "try again", "rate limit", "too many requests",
    " 429", " 502", " 503", " 504",
)


def is_retry_safe(tool: str, operation: str) -> bool:
    """True when re-running the op has no observable side effect, so it is safe
    to auto-retry after a transient error.

    Delegates to the MCP policy's ``is_mutating`` classifier: anything that
    writes local state, executes code, scans, or fires at a target is mutating
    and therefore NOT auto-retried — the model decides whether to re-issue it.
    Only pure reads / queries / recon (filesystem reads, graph queries, process
    stats, clipboard paste, keychain lookups, web reads, arsenal.detect, …)
    are retry-safe.
    """
    return not is_mutating(tool, operation)


def is_transient_error(error: Optional[str]) -> bool:
    """Heuristic: does this error string look like a transient blip?"""
    if not error:
        return False
    e = error.lower()
    return any(marker in e for marker in _TRANSIENT_MARKERS)


# ── Recovery guidance ─────────────────────────────────────────────────────────

def _snippet(error: Optional[str], limit: int = 160) -> str:
    e = (error or "").strip()
    return e if len(e) <= limit else e[:limit] + "…"


def recovery_hint(status: str, tool: str, operation: str, error: Optional[str], attempts: int) -> str:
    """Concrete next-step guidance for a failed tool call, appended to the model
    feedback so KITT self-heals instead of repeating a broken call.

    ``status`` is the ``ToolResultStatus`` value string.
    """
    err = _snippet(error)
    if status in ("policy_denied", "denied"):
        return (
            "RECOVER: Meteor's policy or the danger gate blocked this — do NOT retry the same call. "
            "If it's an offensive op that needs authorisation, tell your partner exactly what scope to set "
            "(e.g. METEOR_MCP_ALLOWED_CIDR) or to approve the action; otherwise reach the objective another way."
        )
    if status == "budget_exhausted":
        return (
            "RECOVER: the signal budget is spent — stop calling tools. Synthesise what you already have "
            "into the final answer now."
        )
    # ERROR (or anything else non-OK).
    if attempts > 1 and is_transient_error(error):
        return (
            f"RECOVER: retried {attempts}× and still failing — looks transient ({err}). "
            "Switch to an alternative tool or route, or proceed with what you already have. "
            "Don't keep hammering the same call."
        )
    return (
        f"RECOVER: this looks like a hard error, not a blip ({err}). Diagnose it — bad params, wrong path, "
        "missing dependency? Fix the call and try once more, or route around it. Do not repeat the identical call."
    )


# ── Plan parsing ────────────────────────────────────────────────────────────

_PLAN_FENCE_RE = re.compile(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", re.IGNORECASE)
_MAX_PLAN_STEPS = 12


def parse_plan(text: str) -> Optional[list[str]]:
    """Extract a KITT plan — a JSON object ``{"plan": [step, ...]}`` — from the
    model's turn, or None if there isn't one.

    Only called on turns with no tool calls, so a plan block is unambiguous.
    Returns the (trimmed, capped) list of step strings.
    """
    candidates: list[str] = []
    for m in _PLAN_FENCE_RE.finditer(text):
        candidates.append(m.group(1))
    stripped = text.strip()
    if stripped.startswith("{"):
        candidates.append(stripped)

    for raw in candidates:
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(data, dict) and isinstance(data.get("plan"), list):
            steps = [str(s).strip() for s in data["plan"] if str(s).strip()]
            if steps:
                return steps[:_MAX_PLAN_STEPS]
    return None

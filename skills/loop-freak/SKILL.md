---
name: loop-freak
description: Loop Freak persona and loopfreak MCP tools — multi-round recon cycles until graph plateaus, aggressive KITT iteration mode. Use for "loop freak", keep looping, spin recon, loopfreak cycle.
---

# Loop Freak

Relentless recon mode for Meteor MCP.

## When to activate

- User says **loop freak**, keep looping, spin until mapped
- Engagement needs multi-pass read recon before active scan
- Agent stopped early and user wants more iterations

## Headless cycle (MCP)

```json
{"tool": "loopfreak", "operation": "cycle", "params": {"max_rounds": 5, "engagement_cidr": "10.0.0.0/24"}}
```

Single round:

```json
{"tool": "loopfreak", "operation": "pulse", "params": {}}
```

## In-app persona

Set `AgentTurn.persona = "loop_freak"` — bumps `max_iterations` to 25 and uses Loop Freak system prompt (`app/agent/loop_freak.py`).

## Standard freak chain

```
loopfreak__cycle → exploit__prioritize → exploit__chain → grinder/nmap (scoped) → exploit__gaps → report
```

## Cursor /loop (session-level)

Recurring local wake every N minutes:

```
/loop 5m Check meteor graph — loopfreak__pulse and graph__counts, report deltas
```

Uses Cursor loop skill; separate from `loopfreak.cycle` inside Meteor.

## References

- Persona: [app/agent/loop_freak.py](../../app/agent/loop_freak.py)
- Runner: [app/loop_freak/runner.py](../../app/loop_freak/runner.py)
- Agent: [agents/loop-freak.md](../../agents/loop-freak.md)

"""Loop Freak — aggressive loop persona + programmatic recon cycles.

Loop Freak is KITT's "don't stop until it's mapped" mode: higher iteration budget,
pushier continue nudges, and a headless ``loopfreak.cycle`` that spins
footprint → intercept → prioritize until the graph plateaus.

NOT autonomous malware or botnet loops — authorized recon only, same MCP gates.
"""

from app.agent.loop_freak import (
    LOOP_FREAK_NAME,
    LoopFreakConfig,
    build_loop_freak_prompt,
    continue_nudge,
)
from app.loop_freak.runner import LoopFreakRunner

__all__ = [
    "LOOP_FREAK_NAME",
    "LoopFreakConfig",
    "LoopFreakRunner",
    "build_loop_freak_prompt",
    "continue_nudge",
]

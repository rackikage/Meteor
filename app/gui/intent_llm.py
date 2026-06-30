"""LLM fallback for ambiguous natural-language intent classification."""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Optional

from app.gui.intent_router import RoutedIntent, _extract_depth, route_intent
from app.models.contract import ModelInput

if TYPE_CHECKING:
    from app.models.registry import ModelRegistry

logger = logging.getLogger(__name__)

INTENT_CLASSIFIER_PROMPT = """You classify user requests for Meteor Interceptor, a local network ops assistant.
Return ONLY valid JSON (no markdown):

{
  "action": "<one of: port_scan|service_enum|vuln_check|investigate|infiltrate|research|graph|pivot|stats|chat>",
  "target": "<ip, cidr, or empty string>",
  "params": {<optional keys: port, service, depth>},
  "reason": "<short rationale>"
}

Mapping hints:
- port_scan / service_enum → scanning hosts or ports
- vuln_check → CVE/exploit research on a service (set params.service)
- investigate → full LAN dig; params.depth 1-3
- chat → general conversation, unclear ops, or off-topic

Use action "chat" when unsure."""

_ACTION_TO_COMMAND: dict[str, str] = {
    "port_scan": "scan",
    "service_enum": "scan",
    "scan": "scan",
    "vuln_check": "research",
    "vulnerability_check": "research",
    "research": "research",
    "investigate": "investigate",
    "infiltrate": "infiltrate",
    "graph": "graph",
    "pivot": "pivot",
    "stats": "stats",
    "help": "help",
    "chat": "chat",
}


def _parse_llm_json(text: str) -> Optional[dict]:
    text = text.strip()
    if not text:
        return None
    candidates = [text]
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        candidates.insert(0, fence.group(1))
    brace = re.search(r"\{.*\}", text, re.DOTALL)
    if brace:
        candidates.append(brace.group(0))
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and "action" in data:
            return data
    return None


def _llm_payload_to_intent(
    data: dict,
    *,
    default_gateway: str,
    default_cidr: str,
    user_text: str,
) -> Optional[RoutedIntent]:
    action = str(data.get("action", "chat")).lower().replace("-", "_")
    if action == "chat":
        return None

    command = _ACTION_TO_COMMAND.get(action)
    if command is None:
        return None

    params = data.get("params") or {}
    if not isinstance(params, dict):
        params = {}

    target = str(data.get("target") or "").strip()
    reason = str(data.get("reason") or f"LLM classified as {action}")

    if command == "scan":
        tgt = target or params.get("target") or default_gateway
        port = params.get("port")
        args: dict = {"target": tgt}
        if port is not None:
            args["port"] = int(port)
        return RoutedIntent(command, args, 0.75, reason)

    if command == "research":
        service = params.get("service") or "smb"
        if "smb" in user_text.lower():
            service = "smb"
        elif "ssh" in user_text.lower():
            service = "ssh"
        return RoutedIntent(command, {"service": str(service).lower()}, 0.75, reason)

    if command == "investigate":
        depth = params.get("depth") or _extract_depth(user_text)
        return RoutedIntent(command, {"depth": int(depth)}, 0.75, reason)

    if command == "infiltrate":
        tgt = target or default_cidr
        depth = params.get("depth") or _extract_depth(user_text)
        return RoutedIntent(command, {"target": tgt, "depth": int(depth)}, 0.75, reason)

    if command == "pivot":
        return RoutedIntent(command, {"ip": target or default_gateway}, 0.75, reason)

    return RoutedIntent(command, {}, 0.75, reason)


def classify_intent_llm(
    text: str,
    model_registry: ModelRegistry,
    *,
    default_gateway: str = "127.0.0.1",
    default_cidr: str = "127.0.0.1/32",
    depth_context: str = "",
) -> Optional[RoutedIntent]:
    """Use ollama-fast to map ambiguous NL to a structured intent."""
    try:
        model = model_registry.get_adapter("ollama-fast")
    except (ValueError, KeyError):
        model = model_registry.resolve_for_request({"complexity": "simple"})

    user_content = text
    if depth_context:
        user_content = f"Prior infiltration context:\n{depth_context}\n\nUser request: {text}"

    result = model.complete(
        ModelInput(
            prompt=user_content,
            system_prompt=INTENT_CLASSIFIER_PROMPT,
            max_tokens=256,
            temperature=0.1,
            metadata={
                "task_mode": "structured",
                "complexity": "simple",
                "profile": "ollama-fast",
                "format": "json",
            },
        )
    )
    data = _parse_llm_json(result.response_text)
    if data is None:
        logger.debug("LLM intent parse failed: %s", result.response_text[:200])
        return None
    return _llm_payload_to_intent(
        data,
        default_gateway=default_gateway,
        default_cidr=default_cidr,
        user_text=text,
    )


def resolve_intent(
    text: str,
    *,
    default_gateway: str = "127.0.0.1",
    default_cidr: str = "127.0.0.1/32",
    model_registry: ModelRegistry | None = None,
    depth_context: str = "",
) -> tuple[str, dict, Optional[RoutedIntent]]:
    """Regex fast-path, then optional LLM fallback. Returns (command, args, routed)."""
    routed = route_intent(
        text,
        default_gateway=default_gateway,
        default_cidr=default_cidr,
    )
    if routed is not None:
        return routed.command, routed.args, routed

    if model_registry is not None:
        routed = classify_intent_llm(
            text,
            model_registry,
            default_gateway=default_gateway,
            default_cidr=default_cidr,
            depth_context=depth_context,
        )
        if routed is not None:
            return routed.command, routed.args, routed

    return "chat", {"prompt": text}, None

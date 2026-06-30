"""Natural-language intent routing for the Meteor chat GUI.

Maps conversational prompts like "dig into the network" to concrete
orchestrator commands (investigate, infiltrate, scan, …).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RoutedIntent:
    command: str
    args: dict
    confidence: float
    reason: str = ""


_INVESTIGATE = (
    r"\b(dig\s+into|investigate|explore|probe|recon|survey|map)\b.*\b(network|lan|subnet|local)\b",
    r"\b(?:deep|thorough|full)\b.*\b(investigation|investigate)\b.*\b(lan|network|subnet)\b",
    r"\bwhat(?:'s| is)\s+on\s+(?:my\s+)?(?:network|lan)\b",
    r"\b(network|lan)\s+(?:recon|investigation|sweep|audit)\b",
    r"\bcheck\s+(?:my\s+)?(?:network|lan|subnet)\b",
    r"\bsweep\s+(?:the\s+)?(?:network|lan|subnet)\b",
)

_INFILTRATE = (
    r"\b(infiltrate|penetrate|compromise|pivot\s+through|breach)\b",
    r"\bgo\s+deep(?:er)?\s+(?:into|on)\b",
    r"\bfull\s+(?:loop|sweep|infiltration)\b",
)

_SCAN = (
    r"\bscan(?:ning)?\b",
    r"\bport\s+sweep\b",
    r"\bprobe\s+(?:the\s+)?(?:gateway|router|host|target)\b",
    r"\bcheck\s+(?:ports?|services?)\b",
)

_RESEARCH = (
    r"\b(research|intel|cve|exploit|vuln(?:erability)?)\b",
    r"\bwhat\s+(?:cves?|exploits?)\b",
    r"\battack\s+surface\b",
)

_GRAPH = (
    r"\b(asset\s+)?graph\b",
    r"\bshow\s+(?:the\s+)?(?:topology|map|assets?)\b",
    r"\bnetwork\s+map\b",
)

_PIVOT = (
    r"\bpivot\b",
    r"\blateral\b",
    r"\bmove\s+(?:to|through)\b",
)

_STATS = (
    r"\b(stats|telemetry|status|health)\b",
    r"\bruntime\s+(?:stats|telemetry)\b",
)

_FIREWALL = (
    r"\b(assess|check|audit|evaluate)\b.*\b(firewall|kernel\s+posture|posture)\b",
    r"\b(firewall|kernel)\b.*\b(posture|assessment|audit)\b",
    r"\b(posture|kernel)\b.*\b(firewall|assessment)\b",
    r"\bufw\b.*\b(status|posture|audit)\b",
    r"\bconntrack\b.*\b(check|audit|posture)\b",
    r"\brp_filter\b",
    r"\baccept_redirects\b",
)

_HELP = (
    r"^(?:help|\?|what\s+can\s+you\s+do)\b",
)


def _match_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def _extract_depth(text: str, default: int = 2) -> int:
    lowered = text.lower()
    if re.search(r"\b(deep|aggressive|thorough|max)\b", lowered):
        return 3
    if re.search(r"\b(quick|light|shallow|passive)\b", lowered):
        return 1
    m = re.search(r"\bdepth\s+(\d+)\b", lowered)
    if m:
        try:
            return max(1, min(int(m.group(1)), 5))
        except ValueError:
            pass
    return default


def _extract_ip(text: str) -> Optional[str]:
    m = re.search(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b", text)
    return m.group(1) if m else None


def _extract_cidr(text: str) -> Optional[str]:
    m = re.search(r"\b(\d{1,3}(?:\.\d{1,3}){3}/\d{1,2})\b", text)
    return m.group(1) if m else None


def _extract_service(text: str) -> str:
    for svc in ("ssh", "smb", "rdp", "http", "https", "ftp", "telnet", "mysql", "postgres"):
        if re.search(rf"\b{svc}\b", text, re.IGNORECASE):
            return svc
    m = re.search(r"(?:research|intel(?:ligence)?|cve(?:s)?\s+for)\s+(\w+)", text, re.IGNORECASE)
    return m.group(1).lower() if m else "ssh"


def route_intent(
    text: str,
    *,
    default_gateway: str = "127.0.0.1",
    default_cidr: str = "127.0.0.1/32",
) -> Optional[RoutedIntent]:
    """Return a structured command if the prompt looks like an ops request."""
    raw = text.strip()
    if not raw:
        return None

    lowered = raw.lower()

    if _match_any(lowered, _HELP):
        return RoutedIntent("help", {}, 1.0, "help request")

    if _match_any(lowered, _STATS):
        return RoutedIntent("stats", {}, 0.9, "telemetry request")

    if _match_any(lowered, _GRAPH):
        return RoutedIntent("graph", {}, 0.9, "asset graph request")

    if _match_any(lowered, _FIREWALL):
        return RoutedIntent("posture", {}, 0.92, "kernel firewall posture assessment")

    if _match_any(lowered, _PIVOT):
        ip = _extract_ip(raw) or default_gateway
        return RoutedIntent("pivot", {"ip": ip}, 0.85, f"pivot to {ip}")

    if _match_any(lowered, _RESEARCH):
        service = _extract_service(raw)
        port_map = {"ssh": 22, "smb": 445, "rdp": 3389, "http": 80, "https": 443, "ftp": 21}
        scan_target = _extract_ip(raw) or default_gateway
        args: dict = {"target": scan_target}
        if service in port_map:
            args["port_hint"] = port_map[service]
        return RoutedIntent("scan", args, 0.85, f"probe {service} on {scan_target}")

    cidr = _extract_cidr(raw)
    ip = _extract_ip(raw)
    depth = _extract_depth(raw)

    if _match_any(lowered, _INFILTRATE) or cidr:
        target = cidr or default_cidr
        return RoutedIntent(
            "infiltrate",
            {"target": target, "depth": depth},
            0.9 if cidr else 0.8,
            f"infiltrate {target}",
        )

    if _match_any(lowered, _INVESTIGATE):
        return RoutedIntent(
            "investigate",
            {"depth": depth},
            0.95,
            "full LAN investigation",
        )

    if _match_any(lowered, _SCAN):
        target = ip or default_gateway
        if re.search(r"\b(gateway|router)\b", lowered, re.IGNORECASE):
            target = default_gateway
        return RoutedIntent("scan", {"target": target}, 0.85, f"scan {target}")

    # Bare IP or hostname without other verbs → scan
    if ip and len(raw.split()) <= 2:
        return RoutedIntent("scan", {"target": ip}, 0.7, f"scan {ip}")

    return None

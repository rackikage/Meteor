from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PolicyAction(str, Enum):
    ALLOW = "allow"
    DENY = "deny"


class PolicySubject(str, Enum):
    RUNTIME = "runtime"
    FILESYSTEM = "filesystem"
    NETWORK = "network"
    MEMORY = "memory"
    INDEX = "index"
    TOOL = "tool"
    MODEL = "model"


@dataclass(frozen=True)
class PolicyRequest:
    subject: PolicySubject
    action: str
    context: dict


@dataclass(frozen=True)
class PolicyDecision:
    action: PolicyAction
    subject: PolicySubject
    reason: str
    audited: bool = True

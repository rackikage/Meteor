"""Tests for LAN network scope discovery."""

from __future__ import annotations

from app.tools.pentest.network_scope import (
    NetworkScope,
    _build_priority_targets,
    _guess_gateway,
    _infer_lan_cidr,
    discover_network_scope,
)


def test_infer_lan_cidr_private() -> None:
    assert _infer_lan_cidr("192.168.1.42") == "192.168.1.0/24"
    assert _infer_lan_cidr("10.0.0.5") == "10.0.0.0/24"


def test_guess_gateway() -> None:
    assert _guess_gateway("192.168.1.42") == "192.168.1.1"
    assert _guess_gateway("10.0.0.5") == "10.0.0.1"


def test_priority_targets_orders_gateway_first() -> None:
    targets = _build_priority_targets("192.168.1.1", "192.168.1.42", "192.168.1.0/24")
    assert targets[0] == "192.168.1.1"
    assert "192.168.1.42" in targets
    assert len(targets) <= 8


def test_discover_network_scope_returns_scope() -> None:
    scope = discover_network_scope()
    assert isinstance(scope, NetworkScope)
    assert scope.gateway
    assert scope.local_ip
    assert scope.cidr
    assert scope.priority_targets
    assert scope.gateway in scope.priority_targets


def test_summary_lines() -> None:
    scope = NetworkScope(
        local_ip="192.168.1.42",
        gateway="192.168.1.1",
        cidr="192.168.1.0/24",
        priority_targets=["192.168.1.1", "192.168.1.42"],
    )
    text = "\n".join(scope.summary_lines())
    assert "192.168.1.1" in text
    assert "192.168.1.0/24" in text

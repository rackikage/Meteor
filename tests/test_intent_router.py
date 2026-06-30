"""Tests for natural-language intent routing in the Meteor GUI."""

from app.gui.intent_router import route_intent


def test_dig_into_network_routes_investigate() -> None:
    intent = route_intent(
        "dig into the network",
        default_gateway="192.168.1.1",
        default_cidr="192.168.1.0/24",
    )
    assert intent is not None
    assert intent.command == "investigate"
    assert intent.args["depth"] == 2


def test_deep_network_investigation_uses_depth_three() -> None:
    intent = route_intent("do a deep investigation of my lan")
    assert intent is not None
    assert intent.command == "investigate"
    assert intent.args["depth"] == 3


def test_scan_gateway_phrasing() -> None:
    intent = route_intent(
        "scan the gateway",
        default_gateway="192.168.1.1",
        default_cidr="192.168.1.0/24",
    )
    assert intent is not None
    assert intent.command == "scan"
    assert intent.args["target"] == "192.168.1.1"


def test_infiltrate_with_cidr() -> None:
    intent = route_intent("infiltrate 10.0.0.0/24 depth 2")
    assert intent is not None
    assert intent.command == "infiltrate"
    assert intent.args["target"] == "10.0.0.0/24"
    assert intent.args["depth"] == 2


def test_research_ssh_maps_to_scan() -> None:
    intent = route_intent("research ssh exploits", default_gateway="192.168.1.1")
    assert intent is not None
    assert intent.command == "scan"


def test_unknown_prompt_returns_none() -> None:
    assert route_intent("what is the weather today") is None

"""Example Meteor plugin — template for custom scan/analyze/report hooks.

Drop any *.py file with PLUGIN_NAME into this directory to activate it.
All three hooks are optional; implement only what you need.

To enable: this file is already in plugins/ and loads automatically.
To disable: rename it to _example_plugin.py (leading underscore skips it).
"""

PLUGIN_NAME    = "example"
PLUGIN_VERSION = "1.0.0"


def scan_hook(ip: str, ports: list[int]) -> list[int]:
    """Called before every host scan.  May add, remove, or reorder ports.

    Example: always probe 9200 (Elasticsearch) when scanning any target.
    """
    extra = [9200, 9300, 5601]   # Elasticsearch / Kibana
    return ports + [p for p in extra if p not in ports]


def analyze_hook(intel: dict) -> dict:
    """Called after each service is researched.

    intel keys: ip, port, service, banner, cves, exploits, attack_surface_score
    Add any key you like — it will be visible in logs but not the GUI.
    """
    score = intel.get("attack_surface_score", 0.0)
    if score >= 7.0:
        intel["risk_label"] = "CRITICAL"
    elif score >= 4.0:
        intel["risk_label"] = "HIGH"
    else:
        intel["risk_label"] = "LOW"
    return intel


def report_hook(report: dict) -> dict:
    """Called once before the final AgentReport is returned.

    report keys mirror AgentReport fields (target, hosts_discovered, etc.)
    Useful for writing to external systems, Slack webhooks, Discord, etc.
    """
    # Example: log a one-liner summary (replace with webhook call, etc.)
    import logging
    log = logging.getLogger("meteor.plugin.example")
    log.info(
        "[example] %s — %d hosts, %d services, %d criticals",
        report.get("target"),
        report.get("hosts_discovered", 0),
        report.get("services_discovered", 0),
        report.get("critical_vulns", 0),
    )
    return report

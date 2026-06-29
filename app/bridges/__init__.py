"""Protocol bridges — native protocol engagement for the infiltration grinder.

Each bridge wraps a system CLI tool (smbclient, ssh, ldapsearch) and publishes
discoveries to the AssetEventBus for graph auto-persistence.
"""


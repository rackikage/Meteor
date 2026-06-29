"""AssetGraph contract — abstract interface for graph persistence.

Meteor Doctrine #4: Contracts outlive implementations. Every adapter
implements this ABC so the orchestrator never depends on a concrete store.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class AssetGraphContract(ABC):
    """Abstract interface for the infiltration grinder asset graph."""

    @abstractmethod
    def upsert_host(self, ip: str, hostname: Optional[str] = None,
                    os: Optional[str] = None, subnet_id: Optional[int] = None,
                    source: Optional[str] = None) -> int:
        """Insert or update a host node. Returns the row id."""
        ...

    @abstractmethod
    def upsert_subnet(self, cidr: str, parent_id: Optional[int] = None,
                      scope_session: Optional[str] = None) -> int:
        """Insert or update a subnet node. Returns the row id."""
        ...

    @abstractmethod
    def upsert_service(self, host_id: int, port: int, name: str,
                       proto: str = "tcp", banner: str = "",
                       state: str = "open") -> int:
        """Insert or update a service node on a host. Returns the row id."""
        ...

    @abstractmethod
    def upsert_credential(self, host_id: Optional[int], username: str,
                          secret_type: str, secret_value: str,
                          source: Optional[str] = None) -> int:
        """Insert or update a credential node. Returns the row id."""
        ...

    @abstractmethod
    def upsert_user(self, name: str, domain: Optional[str] = None,
                    source: Optional[str] = None) -> int:
        """Insert or update a user node. Returns the row id."""
        ...

    @abstractmethod
    def upsert_share(self, host_id: int, name: str, share_type: Optional[str] = None,
                     permissions: Optional[str] = None) -> int:
        """Insert or update a share node. Returns the row id."""
        ...

    @abstractmethod
    def upsert_vulnerability(self, service_id: int, cve_id: str,
                             severity: Optional[str] = None,
                             description: Optional[str] = None,
                             exploit_available: bool = False) -> int:
        """Insert or update a vulnerability node. Returns the row id."""
        ...

    @abstractmethod
    def add_edge(self, source_type: str, source_id: int,
                 target_type: str, target_id: int,
                 edge_type: str, weight: float = 1.0,
                 confidence: float = 1.0) -> None:
        """Add or refresh a typed edge between two nodes."""
        ...

    @abstractmethod
    def add_observation(self, asset_type: str, asset_id: int,
                        source: str, payload: dict[str, Any]) -> None:
        """Record a time-series observation against an asset."""
        ...

    @abstractmethod
    def query(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        """Execute a read-only SQL query against the graph. SELECT only."""
        ...

    @abstractmethod
    def find_neighbors(self, asset_type: str, asset_id: int,
                       edge_type: Optional[str] = None) -> list[dict[str, Any]]:
        """Return all nodes connected to the given asset by edges."""
        ...

    @abstractmethod
    def find_paths(self, source_type: str, source_id: int,
                   target_type: str, target_id: int,
                   max_hops: int = 4) -> list[dict[str, Any]]:
        """Find all paths between two nodes using recursive CTE."""
        ...

    @abstractmethod
    def close(self) -> None:
        """Close any open resources."""
        ...

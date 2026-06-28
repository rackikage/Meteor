from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class RetrievalQuery:
    query_text: str
    top_k: int = 5
    metadata_filters: dict = field(default_factory=dict)


@dataclass
class RetrievedDocument:
    content: str
    source: str
    score: float
    metadata: dict = field(default_factory=dict)


@dataclass
class RetrievalResult:
    query: RetrievalQuery
    documents: list[RetrievedDocument] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class RetrievalAdapter(ABC):
    """Abstract interface. All retrieval backends must implement this contract."""

    @abstractmethod
    def query(self, query: RetrievalQuery) -> RetrievalResult:
        ...

    @abstractmethod
    def index(self, documents: list[dict]) -> None:
        ...

    @abstractmethod
    def health(self) -> dict:
        ...

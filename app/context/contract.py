from __future__ import annotations

from dataclasses import dataclass, field

from app.memory.contract import MemoryEntry
from app.retrieval.contract import RetrievedDocument


@dataclass
class RuntimeContext:
    prompt: str
    session_id: str
    memory: list[MemoryEntry] = field(default_factory=list)
    documents: list[RetrievedDocument] = field(default_factory=list)
    policy_trace: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_model_context(self) -> list[dict]:
        items: list[dict] = []
        for entry in self.memory:
            items.append(
                {
                    "type": "memory",
                    "memory_type": entry.memory_type.value,
                    "content": entry.content,
                    "timestamp": entry.timestamp,
                    "metadata": entry.metadata,
                }
            )
        for document in self.documents:
            items.append(
                {
                    "type": "retrieved_document",
                    "source": document.source,
                    "content": document.content,
                    "score": document.score,
                    "metadata": document.metadata,
                }
            )
        return items

from __future__ import annotations

from app.context.contract import RuntimeContext
from app.memory.contract import MemoryEntry
from app.retrieval.contract import RetrievedDocument
from app.runtime.contract import RuntimeRequest


class ContextBuilder:
    """Builds the model-ready context without calling retrieval or model adapters."""

    def __init__(self, max_items: int = 20) -> None:
        self._max_items = max_items

    def build(
        self,
        request: RuntimeRequest,
        memory: list[MemoryEntry],
        documents: list[RetrievedDocument],
        policy_trace: list[dict],
    ) -> RuntimeContext:
        selected_memory = memory[: self._max_items]
        remaining = max(self._max_items - len(selected_memory), 0)
        selected_documents = documents[:remaining]
        return RuntimeContext(
            prompt=request.prompt,
            session_id=request.session_id,
            memory=selected_memory,
            documents=selected_documents,
            policy_trace=policy_trace,
            metadata={
                "memory_count": len(selected_memory),
                "document_count": len(selected_documents),
                "max_items": self._max_items,
            },
        )

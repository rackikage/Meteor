"""Context Builder — assemble memory, retrieval, and evidence into model-ready prompts.

Meteor Doctrine #5: Memory is infrastructure. Doctrine #6: Retrieval is separate
from inference. This layer bridges them — it takes the user's raw prompt, loads
relevant conversation history, retrieves matching documents, scores evidence, and
assembles everything into a structured prompt the model can reason over.

The model never performs retrieval. It never queries memory directly. It receives
a pre-built context from this builder — clean separation of concerns.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from app.evidence.tracker import EvidenceTracker
from app.memory.contract import MemoryAdapter, MemoryType
from app.memory.sqlite_adapter import SQLiteMemoryAdapter
from app.retrieval.contract import RetrievedDocument, RetrievalAdapter, RetrievalQuery

logger = logging.getLogger(__name__)


@dataclass
class BuiltContext:
    """Assembled context ready for model consumption.

    Contains:
    - system_prompt: instructions for the model
    - conversation_history: previous messages in this session
    - retrieved_documents: relevant indexed documents
    - evidence: scored evidence for any claims in context
    - final_prompt: the complete prompt string ready for ModelInput
    """
    session_id: str
    system_prompt: str = ""
    user_prompt: str = ""
    conversation_history: list[dict] = field(default_factory=list)
    retrieved_documents: list[RetrievedDocument] = field(default_factory=list)
    corrections: list[dict] = field(default_factory=list)
    episodic_events: list[dict] = field(default_factory=list)
    project_state: dict = field(default_factory=dict)
    evidence: list[dict] = field(default_factory=list)
    final_prompt: str = ""
    metadata: dict = field(default_factory=dict)

    def to_model_input(self, max_tokens: int = 512, temperature: float = 0.7) -> dict:
        """Convert to ModelInput-compatible dict."""
        from app.models.contract import ModelInput
        return ModelInput(
            prompt=self.final_prompt,
            context=self.conversation_history,
            max_tokens=max_tokens,
            temperature=temperature,
            metadata=self.metadata,
        )


class ContextBuilder:
    """Assembles model-ready context from memory and retrieval.

    The pipeline:
    1. Load conversation history for the session
    2. Load corrections (user feedback) for the session
    3. Load episodic memory events
    4. Search retrieval index for relevant documents
    5. Score evidence for retrieved documents
    6. Assemble everything into a structured prompt

    Usage:
        builder = ContextBuilder(memory=memory, retrieval=retrieval)
        ctx = builder.build("user-session-1", "What is machine learning?")
        model_input = ctx.to_model_input()
    """

    DEFAULT_SYSTEM_PROMPT = (
        "You are Meteor, a local-first AI assistant running entirely on this machine. "
        "All data stays local. You have access to conversation history, indexed documents, "
        "and user corrections. When citing information, reference the source if available. "
        "Be concise and direct."
    )

    def __init__(
        self,
        memory: MemoryAdapter,
        retrieval: Optional[RetrievalAdapter] = None,
        evidence_tracker: Optional[EvidenceTracker] = None,
        system_prompt: Optional[str] = None,
        max_history_messages: int = 20,
        max_retrieved_docs: int = 5,
        max_corrections: int = 3,
    ) -> None:
        self.memory = memory
        self.retrieval = retrieval
        self.evidence_tracker = evidence_tracker or EvidenceTracker()
        self.system_prompt = system_prompt or self.DEFAULT_SYSTEM_PROMPT
        self.max_history_messages = max_history_messages
        self.max_retrieved_docs = max_retrieved_docs
        self.max_corrections = max_corrections

    def build(self, session_id: str, user_prompt: str, metadata: Optional[dict] = None) -> BuiltContext:
        """Build a complete context for a user prompt.

        Returns a BuiltContext with all layers assembled and a final_prompt
        string ready for model consumption.
        """
        ctx = BuiltContext(
            session_id=session_id,
            system_prompt=self.system_prompt,
            user_prompt=user_prompt,
            metadata=metadata or {},
        )

        # Layer 1: Load conversation history
        ctx.conversation_history = self._load_conversation(session_id)

        # Layer 2: Load corrections (user feedback on prior responses)
        ctx.corrections = self._load_corrections(session_id)

        # Layer 3: Load episodic memory events
        ctx.episodic_events = self._load_episodic(session_id)

        # Layer 4: Search retrieval index
        if self.retrieval:
            ctx.retrieved_documents = self._search_retrieval(user_prompt)
            ctx.metadata["retrieved_count"] = len(ctx.retrieved_documents)

        # Layer 5: Annotate with evidence
        if ctx.retrieved_documents:
            claim = self.evidence_tracker.annotate_response_with_evidence(
                response_text=user_prompt,
                retrieved_documents=ctx.retrieved_documents,
            )
            ctx.evidence = [
                {
                    "source": e.source,
                    "content": e.content[:200],
                    "confidence": e.confidence.value,
                    "trace": e.trace,
                }
                for e in claim.evidence[:5]
            ]
            ctx.metadata["evidence_count"] = len(ctx.evidence)

        # Assemble final prompt
        ctx.final_prompt = self._assemble_prompt(ctx)

        logger.info(
            "Context built: session=%s, history=%d, retrieval=%d, corrections=%d, evidence=%d",
            session_id,
            len(ctx.conversation_history),
            len(ctx.retrieved_documents),
            len(ctx.corrections),
            len(ctx.evidence),
        )

        return ctx

    def _load_conversation(self, session_id: str) -> list[dict]:
        """Load recent conversation history for a session."""
        entries = self.memory.read(session_id, MemoryType.CONVERSATION)
        recent = entries[-self.max_history_messages:]
        return [
            {
                "role": e.metadata.get("role", "user"),
                "content": e.content,
                "timestamp": e.timestamp,
            }
            for e in recent
        ]

    def _load_corrections(self, session_id: str) -> list[dict]:
        """Load user corrections for this session."""
        entries = self.memory.read(session_id, MemoryType.CORRECTION)
        recent = entries[-self.max_corrections:]
        return [
            {
                "original": e.metadata.get("original", ""),
                "corrected": e.content,
                "reason": e.metadata.get("reason", ""),
                "timestamp": e.timestamp,
            }
            for e in recent
        ]

    def _load_episodic(self, session_id: str) -> list[dict]:
        """Load episodic memory events for this session."""
        entries = self.memory.read(session_id, MemoryType.EPISODIC)
        return [
            {
                "event_type": e.metadata.get("event_type", ""),
                "content": e.content[:200],
                "timestamp": e.timestamp,
            }
            for e in entries[-10:]
        ]

    def _search_retrieval(self, query: str) -> list[RetrievedDocument]:
        """Search the retrieval index for relevant documents."""
        if not self.retrieval:
            return []

        rq = RetrievalQuery(query_text=query, top_k=self.max_retrieved_docs)
        result = self.retrieval.query(rq)
        return result.documents

    def _assemble_prompt(self, ctx: BuiltContext) -> str:
        """Assemble all context layers into a single model-ready prompt."""
        parts = []

        # System prompt
        parts.append(f"System: {ctx.system_prompt}")

        # Corrections (user feedback on prior answers)
        if ctx.corrections:
            parts.append("\nUser corrections (apply these going forward):")
            for c in ctx.corrections:
                parts.append(f"  - Original: {c['original']}")
                parts.append(f"    Corrected to: {c['corrected']}")
                if c["reason"]:
                    parts.append(f"    Reason: {c['reason']}")

        # Episodic events (context about what happened in this session)
        if ctx.episodic_events:
            events_summary = "; ".join(
                e["content"][:100] for e in ctx.episodic_events[-3:]
            )
            parts.append(f"\nSession context: {events_summary}")

        # Retrieved documents (relevant indexed knowledge)
        if ctx.retrieved_documents:
            parts.append("\nRelevant information from the local index:")
            for i, doc in enumerate(ctx.retrieved_documents, 1):
                parts.append(f"\n  [{i}] Source: {doc.source} (score: {doc.score:.2f})")
                parts.append(f"  {doc.content[:500]}")

        # Evidence annotations
        if ctx.evidence:
            parts.append("\nEvidence for context:")
            for e in ctx.evidence:
                parts.append(f"  - Source: {e['source']} (confidence: {e['confidence']})")

        # Conversation history
        if ctx.conversation_history:
            parts.append("\nConversation history:")
            for msg in ctx.conversation_history:
                role = msg["role"]
                content = msg["content"][:500]
                parts.append(f"  [{role}]: {content}")

        # User prompt
        parts.append(f"\nUser: {ctx.user_prompt}")
        parts.append("\nAssistant:")

        return "\n".join(parts)

    def build_quick(self, session_id: str, user_prompt: str) -> str:
        """Quick context build — just system prompt + history + user prompt.

        Skips retrieval for fast responses.
        """
        ctx = self.build(session_id, user_prompt)
        history_part = []
        for msg in ctx.conversation_history[-6:]:
            history_part.append(f"[{msg['role']}]: {msg['content'][:300]}")

        prompt = f"System: {self.system_prompt}\n\n"
        if history_part:
            prompt += "Conversation history:\n" + "\n".join(history_part) + "\n\n"
        prompt += f"User: {user_prompt}\nAssistant:"
        return prompt

    def health(self) -> dict:
        return {
            "healthy": True,
            "max_history_messages": self.max_history_messages,
            "max_retrieved_docs": self.max_retrieved_docs,
            "max_corrections": self.max_corrections,
            "has_retrieval": self.retrieval is not None,
        }

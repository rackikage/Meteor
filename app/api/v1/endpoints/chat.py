"""Chat endpoint — completion and streaming responses.

Provides:
- POST /chat — single completion
- POST /chat/stream — streaming completion (SSE)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    prompt: str
    session_id: Optional[str] = None
    max_tokens: int = Field(default=512, ge=1, le=4096)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    stream: bool = False
    metadata: dict = Field(default_factory=dict)


class ChatResponse(BaseModel):
    response_text: str
    finish_reason: str
    token_usage: dict
    session_id: str
    metadata: dict


class StreamChunk(BaseModel):
    token: str
    session_id: str
    done: bool = False


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Run a single completion and return the full response."""
    from app.api.main import get_runtime
    runtime = get_runtime()

    session_id = request.session_id or f"session-{datetime.now(timezone.utc).timestamp()}"

    try:
        result = runtime.handle_chat(
            prompt=request.prompt,
            session_id=session_id,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            metadata=request.metadata,
        )
    except Exception as exc:
        return ChatResponse(
            response_text=f"[Meteor]: {exc}",
            finish_reason="error",
            token_usage={"total_tokens": 0},
            session_id=session_id,
            metadata={"error": str(exc)},
        )

    return ChatResponse(
        response_text=result["response_text"],
        finish_reason=result["finish_reason"],
        token_usage=result["token_usage"],
        session_id=session_id,
        metadata=result["metadata"],
    )


@router.post("/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """Stream tokens as they are generated (Server-Sent Events)."""
    from app.api.main import get_runtime
    runtime = get_runtime()

    session_id = request.session_id or f"session-{datetime.now(timezone.utc).timestamp()}"

    def generate():
        for token in runtime.handle_chat_stream(
            prompt=request.prompt,
            session_id=session_id,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            metadata=request.metadata,
        ):
            chunk = StreamChunk(token=token, session_id=session_id, done=False)
            yield f"data: {chunk.model_dump_json()}\n\n"

        done_chunk = StreamChunk(token="", session_id=session_id, done=True)
        yield f"data: {done_chunk.model_dump_json()}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

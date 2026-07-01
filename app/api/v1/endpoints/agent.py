"""Agent SSE endpoint — streams AgentChatLoop events to the web UI."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator, Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agent.chatbot_loop import AgentChatLoop, AgentTurn, ChatMessage
from app.tools.system.registry import get_registry

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agent", tags=["agent"])


# ── In-memory session history ────────────────────────────────────────
# One rolling deque per session_id. Fine for a local single-user app.
_SESSIONS: dict[str, list[ChatMessage]] = {}
_MAX_HISTORY = 20


class ChatRequest(BaseModel):
    prompt: str
    session_id: str = "web-default"
    max_tokens: int = 2048
    temperature: float = 0.5
    max_iterations: int = 12


@router.post("/chat")
async def chat(req: ChatRequest) -> StreamingResponse:
    """Run one agent turn, streaming events as Server-Sent Events."""
    from app.api.main import get_runtime
    runtime = get_runtime()
    model = runtime.model_registry.get_adapter(_ACTIVE_PROFILE["name"])
    loop_obj = AgentChatLoop(model=model, tools=runtime.tool_executor)

    history = list(_SESSIONS.get(req.session_id, []))[-12:]
    turn = AgentTurn(
        prompt=req.prompt,
        session_id=req.session_id,
        history=history,
        max_iterations=req.max_iterations,
        max_tokens=req.max_tokens,
        temperature=req.temperature,
    )

    async def stream() -> AsyncIterator[bytes]:
        event_loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def on_event(kind: str, payload: dict) -> None:
            # Called from the worker thread — hop back onto the event loop.
            event_loop.call_soon_threadsafe(queue.put_nowait, (kind, payload))

        final_holder: dict[str, str] = {}

        async def run_agent() -> None:
            try:
                final_text, _ = await asyncio.to_thread(loop_obj.run, turn, on_event)
                final_holder["text"] = final_text or ""
            except Exception as exc:
                logger.exception("Agent loop crashed")
                event_loop.call_soon_threadsafe(queue.put_nowait, ("error", {"message": str(exc)}))
            finally:
                event_loop.call_soon_threadsafe(queue.put_nowait, (None, None))

        agent_task = asyncio.create_task(run_agent())

        try:
            while True:
                kind, payload = await queue.get()
                if kind is None:
                    break
                yield _sse(kind, payload)

            # Persist history after the turn completes.
            if final_holder.get("text"):
                bucket = _SESSIONS.setdefault(req.session_id, [])
                bucket.append(ChatMessage(role="user", content=req.prompt))
                bucket.append(ChatMessage(role="assistant", content=final_holder["text"]))
                _SESSIONS[req.session_id] = bucket[-_MAX_HISTORY:]

            yield _sse("done", {})
        finally:
            if not agent_task.done():
                agent_task.cancel()

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# Runtime override for the active profile — the GUI's fast/smart toggle writes
# here and every subsequent /agent/chat call resolves the model through it.
_ACTIVE_PROFILE: dict[str, Optional[str]] = {"name": None}


def _current_profile_name(reg) -> str:
    return _ACTIVE_PROFILE["name"] or reg._effective_default_profile()


class ModelSwitchRequest(BaseModel):
    profile: Optional[str] = None
    role: Optional[str] = None  # "fast" | "heavy"


@router.get("/model")
async def active_model() -> dict:
    """Return the effective model + backend so the UI can label it."""
    from app.api.main import get_runtime
    runtime = get_runtime()
    reg = runtime.model_registry
    profile_name = _current_profile_name(reg)
    profile = reg.config.models.profiles[profile_name]
    return {
        # Meteor presents itself as a single model, "Meteor" — the underlying
        # engine (Pollinations / Groq / Ollama / …) is an implementation detail.
        "model": "Meteor",
        "profile": profile_name,
        "backend": profile.backend,
        "engine": profile.model_path,
        "context_window": profile.context_window,
        "role": profile.role,
        "available": [
            {"profile": n, "engine": p.model_path, "role": p.role, "backend": p.backend}
            for n, p in reg.config.models.profiles.items()
        ],
    }


@router.post("/model")
async def switch_model(req: ModelSwitchRequest) -> dict:
    """Switch the active model profile. Accepts either `profile` (exact name)
    or `role` ("fast" / "heavy") to pick the first matching local profile."""
    from app.api.main import get_runtime
    runtime = get_runtime()
    reg = runtime.model_registry
    target: Optional[str] = None
    if req.profile:
        if req.profile not in reg.config.models.profiles:
            return {"ok": False, "error": f"unknown profile: {req.profile}"}
        target = req.profile
    elif req.role:
        for name, prof in reg.config.models.profiles.items():
            if prof.role == req.role and prof.backend.lower() == "ollama":
                target = name
                break
        if target is None:
            for name, prof in reg.config.models.profiles.items():
                if prof.role == req.role:
                    target = name
                    break
    if target is None:
        return {"ok": False, "error": "no matching profile"}
    _ACTIVE_PROFILE["name"] = target
    profile = reg.config.models.profiles[target]
    return {
        "ok": True,
        "profile": target,
        "model": profile.model_path,
        "role": profile.role,
        "backend": profile.backend,
    }


@router.get("/tools")
async def list_tools() -> dict:
    """Return the registered tool set for the /tools panel."""
    return {"tools": get_registry().list_tools()}


@router.post("/clear")
async def clear_session(session_id: str = "web-default") -> dict:
    _SESSIONS.pop(session_id, None)
    return {"ok": True, "session_id": session_id}


def _sse(event: str, payload: Any) -> bytes:
    body = json.dumps(payload, default=str)
    return f"event: {event}\ndata: {body}\n\n".encode("utf-8")

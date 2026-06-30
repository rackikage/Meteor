"""Depth-controlled context building for multi-step infiltration ops."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from app.config import ModelProfile
from app.models.contract import ModelAdapter, ModelInput, ModelOutput
from app.models.task_temperature import resolve_temperature
from app.runtime.interceptor_prompt import DEPTH_SUMMARY_PROMPT, NEXT_COMMAND_PROMPT

logger = logging.getLogger(__name__)


@dataclass
class DepthStep:
    name: str
    output: str
    summary: str = ""


@dataclass
class DepthSession:
    max_depth: int
    steps: list[DepthStep] = field(default_factory=list)

    def history_text(self, max_chars: int = 1200) -> str:
        lines = []
        for step in self.steps:
            body = step.summary or step.output[:200]
            lines.append(f"- {step.name}: {body}")
        text = "\n".join(lines)
        return text[-max_chars:]


class DepthContextManager:
    """Iteratively summarize results and suggest next commands at high depth."""

    def __init__(
        self,
        model: ModelAdapter,
        profile: ModelProfile,
        max_summary_chars: int = 400,
    ) -> None:
        self._model = model
        self._profile = profile
        self._max_summary_chars = max_summary_chars

    def record_step(self, session: DepthSession, name: str, output: str) -> str:
        """Summarize a step and append to session history."""
        summary = self.summarize_step(name, output, session.max_depth, len(session.steps) + 1)
        session.steps.append(DepthStep(name=name, output=output, summary=summary))
        return summary

    def summarize_step(
        self,
        step_name: str,
        output: str,
        max_depth: int,
        current_depth: int,
    ) -> str:
        """Compress intermediate output to avoid context overflow."""
        if len(output) <= self._max_summary_chars:
            return output.strip()

        prompt = DEPTH_SUMMARY_PROMPT.format(
            step_name=step_name,
            max_depth=max_depth,
            current_depth=current_depth,
            output=output[:3000],
        )
        result = self._model.complete(
            ModelInput(
                prompt=prompt,
                max_tokens=min(256, self._profile.max_tokens),
                temperature=resolve_temperature(self._profile, {"task_mode": "structured"}),
                metadata={"task_mode": "structured"},
            )
        )
        text = result.response_text.strip()
        return text[: self._max_summary_chars] if text else output[: self._max_summary_chars]

    def suggest_next_command(self, session: DepthSession) -> Optional[dict]:
        """Use the model to propose the next structured intent."""
        if len(session.steps) >= session.max_depth:
            return None

        prompt = NEXT_COMMAND_PROMPT.format(
            current_depth=len(session.steps),
            max_depth=session.max_depth,
            history=session.history_text(),
        )
        result = self._model.complete(
            ModelInput(
                prompt=prompt,
                max_tokens=128,
                temperature=resolve_temperature(self._profile, {"task_mode": "structured"}),
                metadata={"task_mode": "structured", "complexity": "simple"},
            )
        )
        return _parse_intent_json(result)

    def build_context_block(self, session: DepthSession) -> str:
        """Format compressed history for injection into a larger prompt."""
        if not session.steps:
            return ""
        lines = ["Infiltration progress (compressed):"]
        for step in session.steps:
            lines.append(f"  [{step.name}] {step.summary or step.output[:120]}")
        return "\n".join(lines)


def _parse_intent_json(output: ModelOutput) -> Optional[dict]:
    text = output.response_text.strip()
    if not text:
        return None

    candidates = [text]
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        candidates.insert(0, fence.group(1))
    brace = re.search(r"\{.*\}", text, re.DOTALL)
    if brace:
        candidates.append(brace.group(0))

    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and "intent" in data:
            return data
    return None

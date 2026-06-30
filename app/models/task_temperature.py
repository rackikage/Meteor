"""Task-aware temperature selection for model inference."""

from __future__ import annotations

from app.config import ModelProfile


def resolve_temperature(profile: ModelProfile, metadata: dict | None = None) -> float:
    """Pick temperature from task mode or explicit override in metadata."""
    meta = metadata or {}
    if "temperature" in meta:
        return float(meta["temperature"])

    mode = meta.get("task_mode", "default")
    if mode == "structured":
        return profile.temperature_structured
    if mode == "creative":
        return profile.temperature_creative
    return profile.temperature

"""Model registry — factory for building model adapters from config profiles.

Meteor Doctrine #3: Adapters isolate change. The registry selects the appropriate
adapter implementation based on the profile's backend type. Adding a new backend
(Ollama, OpenAI, Anthropic) requires only a new adapter file and a registry entry.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from app.config import MeteorConfig, ModelProfile
from app.models.contract import ModelAdapter

logger = logging.getLogger(__name__)


_OPENAI_COMPATIBLE_BACKENDS = {"groq", "cerebras", "openrouter", "together", "gemini_openai", "pollinations"}
_BACKEND_KEY_ENV = {
    "groq": "GROQ_API_KEY",
    "cerebras": "CEREBRAS_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "together": "TOGETHER_API_KEY",
    "gemini_openai": "GEMINI_API_KEY",
}


class ModelRegistry:
    """Registry of model adapters. Builds and caches adapters by profile name."""

    def __init__(self, config: MeteorConfig, repo_root: Path) -> None:
        self.config = config
        self.repo_root = repo_root
        self._adapters: dict[str, ModelAdapter] = {}

    def get_adapter(self, profile_name: Optional[str] = None) -> ModelAdapter:
        """Get or build a model adapter for the given profile.
        If profile_name is None, uses the effective default profile — which
        auto-upgrades to the fastest available hosted profile when its API key
        is present in the environment.
        """
        if profile_name is None:
            profile_name = self._effective_default_profile()

        if profile_name in self._adapters:
            return self._adapters[profile_name]

        profile = self.config.models.profiles.get(profile_name)
        if profile is None:
            raise ValueError(f"Model profile '{profile_name}' not found in config")

        adapter = self._build_adapter(profile)
        self._adapters[profile_name] = adapter
        logger.info("Built adapter for profile: %s (backend=%s)", profile_name, profile.backend)
        return adapter

    def _effective_default_profile(self) -> str:
        """Prefer a hosted-free profile if its API key is set; else config default.

        Priority: Groq (fastest) → Cerebras → Gemini → Together → OpenRouter → config default.
        """
        priority = ("groq", "cerebras", "gemini_openai", "together", "openrouter")
        for backend in priority:
            env_var = _BACKEND_KEY_ENV[backend]
            if not os.environ.get(env_var, "").strip():
                continue
            # Prefer a profile flagged role="fast" on that backend, else any profile on it.
            fast_pick = None
            any_pick = None
            for name, prof in self.config.models.profiles.items():
                if prof.backend.lower() != backend:
                    continue
                if prof.role == "fast" and fast_pick is None:
                    fast_pick = name
                elif any_pick is None:
                    any_pick = name
            picked = fast_pick or any_pick
            if picked:
                logger.info("Auto-selected hosted default profile: %s (%s key present)", picked, env_var)
                return picked
        return self.config.models.default_profile

    def profile_for_role(self, role: str) -> Optional[str]:
        """Pick the best available profile for a role ("fast"/"heavy"): a hosted
        backend whose key is set (Groq → Cerebras → Gemini → Together →
        OpenRouter), then keyless Pollinations, then any other match. Local
        inference profiles are not shipped with Meteor's default config, so
        this path never has to hit Ollama."""
        profiles = self.config.models.profiles
        priority = ("groq", "cerebras", "gemini_openai", "together", "openrouter")
        for backend in priority:
            env_var = _BACKEND_KEY_ENV[backend]
            if not os.environ.get(env_var, "").strip():
                continue
            for name, prof in profiles.items():
                if prof.backend.lower() == backend and prof.role == role:
                    return name
        for name, prof in profiles.items():
            if prof.backend.lower() == "pollinations" and prof.role == role:
                return name
        for name, prof in profiles.items():
            if prof.role == role:
                return name
        return None

    def resolve_for_request(self, metadata: Optional[dict] = None) -> ModelAdapter:
        """Route simple tasks to a fast profile; complex ops to default/heavy."""
        meta = metadata or {}
        if meta.get("profile"):
            return self.get_adapter(str(meta["profile"]))

        complexity = meta.get("complexity", "standard")
        if complexity == "simple":
            for name, profile in self.config.models.profiles.items():
                if profile.role == "fast":
                    return self.get_adapter(name)

        if complexity == "heavy":
            for name, profile in self.config.models.profiles.items():
                if profile.role == "heavy":
                    return self.get_adapter(name)

        return self.get_adapter()

    def _build_adapter(self, profile: ModelProfile) -> ModelAdapter:
        """Build an adapter based on the profile's backend type."""
        backend = profile.backend.lower()

        if backend == "llama_cpp":
            from app.models.llama_cpp_adapter import build_llama_cpp_adapter
            return build_llama_cpp_adapter(profile, self.repo_root)

        elif backend == "ollama":
            from app.models.ollama_adapter import build_ollama_adapter
            return build_ollama_adapter(profile)

        elif backend in _OPENAI_COMPATIBLE_BACKENDS:
            from app.models.groq_adapter import build_openai_compatible_adapter
            return build_openai_compatible_adapter(profile, backend)

        elif backend in ("openai", "anthropic", "remote"):
            raise NotImplementedError(
                f"Backend '{backend}' is not yet implemented. "
                "Contributions welcome!"
            )

        else:
            raise ValueError(f"Unknown model backend: {backend}")

    def health(self) -> dict:
        """Return health status of all registered adapters.

        Includes a top-level `healthy` bool (true iff every registered
        profile reports healthy) so callers aggregating multiple components
        via `.get("healthy", False)` see an accurate status instead of
        always defaulting to unhealthy.
        """
        profiles = {}
        for name, adapter in self._adapters.items():
            profiles[name] = adapter.health()
        all_healthy = all(p.get("healthy", False) for p in profiles.values()) if profiles else False
        return {"healthy": all_healthy, "profiles": profiles}

    def list_profiles(self) -> list[str]:
        """List all available model profile names."""
        return list(self.config.models.profiles.keys())


def build_model_registry(config: MeteorConfig, repo_root: Path) -> ModelRegistry:
    """Factory function to build a ModelRegistry."""
    return ModelRegistry(config, repo_root)

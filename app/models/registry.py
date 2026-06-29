"""Model registry — factory for building model adapters from config profiles.

Meteor Doctrine #3: Adapters isolate change. The registry selects the appropriate
adapter implementation based on the profile's backend type. Adding a new backend
(Ollama, OpenAI, Anthropic) requires only a new adapter file and a registry entry.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from app.config import MeteorConfig, ModelProfile
from app.models.contract import ModelAdapter

logger = logging.getLogger(__name__)


class ModelRegistry:
    """Registry of model adapters. Builds and caches adapters by profile name."""

    def __init__(self, config: MeteorConfig, repo_root: Path) -> None:
        self.config = config
        self.repo_root = repo_root
        self._adapters: dict[str, ModelAdapter] = {}

    def get_adapter(self, profile_name: Optional[str] = None) -> ModelAdapter:
        """Get or build a model adapter for the given profile.
        If profile_name is None, uses the default profile from config.
        """
        if profile_name is None:
            profile_name = self.config.models.default_profile

        if profile_name in self._adapters:
            return self._adapters[profile_name]

        profile = self.config.models.profiles.get(profile_name)
        if profile is None:
            raise ValueError(f"Model profile '{profile_name}' not found in config")

        adapter = self._build_adapter(profile)
        self._adapters[profile_name] = adapter
        logger.info("Built adapter for profile: %s (backend=%s)", profile_name, profile.backend)
        return adapter

    def _build_adapter(self, profile: ModelProfile) -> ModelAdapter:
        """Build an adapter based on the profile's backend type."""
        backend = profile.backend.lower()

        if backend == "llama_cpp":
            from app.models.llama_cpp_adapter import build_llama_cpp_adapter
            return build_llama_cpp_adapter(profile, self.repo_root)

        elif backend == "ollama":
            from app.models.ollama_adapter import build_ollama_adapter
            return build_ollama_adapter(profile)

        elif backend in ("openai", "anthropic", "remote"):
            raise NotImplementedError(
                f"Backend '{backend}' is not yet implemented. "
                "Contributions welcome!"
            )

        else:
            raise ValueError(f"Unknown model backend: {backend}")

    def health(self) -> dict:
        """Return health status of all registered adapters."""
        health = {}
        for name, adapter in self._adapters.items():
            health[name] = adapter.health()
        return health

    def list_profiles(self) -> list[str]:
        """List all available model profile names."""
        return list(self.config.models.profiles.keys())


def build_model_registry(config: MeteorConfig, repo_root: Path) -> ModelRegistry:
    """Factory function to build a ModelRegistry."""
    return ModelRegistry(config, repo_root)

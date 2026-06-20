from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class AppConfig:
    name: str
    version: str
    local_first: bool
    debug: bool


@dataclass
class ModelProfile:
    backend: str
    model_path: str
    context_window: int
    temperature: float
    max_tokens: int
    wired: bool


@dataclass
class ModelsConfig:
    default_profile: str
    profiles: dict[str, ModelProfile]


@dataclass
class PolicyAllowRule:
    subject: str
    action: str
    paths: list[str] = field(default_factory=list)


@dataclass
class PolicyConfig:
    default_action: str
    allow_rules: list[PolicyAllowRule]


@dataclass
class MemoryConfig:
    backend: str
    path: str


@dataclass
class RetrievalConfig:
    backend: str
    index_path: str


@dataclass
class StoragePaths:
    memory: str
    audit: str
    index_meta: str


@dataclass
class StorageConfig:
    backend: str
    paths: StoragePaths


@dataclass
class ObservabilityConfig:
    log_level: str
    audit_enabled: bool
    health_checks_enabled: bool


@dataclass
class MeteorConfig:
    app: AppConfig
    models: ModelsConfig
    policy: PolicyConfig
    memory: MemoryConfig
    retrieval: RetrievalConfig
    storage: StorageConfig
    observability: ObservabilityConfig

    @classmethod
    def load(cls, config_path: Path) -> "MeteorConfig":
        with open(config_path, "r") as f:
            raw: dict[str, Any] = yaml.safe_load(f)

        app = AppConfig(**raw["app"])

        profiles = {
            name: ModelProfile(**profile_data)
            for name, profile_data in raw["models"]["profiles"].items()
        }
        models = ModelsConfig(
            default_profile=raw["models"]["default_profile"],
            profiles=profiles,
        )

        allow_rules = [
            PolicyAllowRule(**rule) for rule in raw["policy"].get("allow_rules", [])
        ]
        policy = PolicyConfig(
            default_action=raw["policy"]["default_action"],
            allow_rules=allow_rules,
        )

        memory = MemoryConfig(**raw["memory"])
        retrieval = RetrievalConfig(**raw["retrieval"])

        storage_paths = StoragePaths(**raw["storage"]["paths"])
        storage = StorageConfig(
            backend=raw["storage"]["backend"],
            paths=storage_paths,
        )

        observability = ObservabilityConfig(**raw["observability"])

        return cls(
            app=app,
            models=models,
            policy=policy,
            memory=memory,
            retrieval=retrieval,
            storage=storage,
            observability=observability,
        )

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
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
    base_url: str = "http://localhost:11434"
    temperature_structured: float = 0.2
    temperature_creative: float = 0.8
    role: str = "default"


@dataclass
class ModelsConfig:
    default_profile: str
    profiles: dict[str, ModelProfile]


@dataclass
class PolicyConfig:
    default_action: str


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

        profile_fields = {f.name for f in dataclasses.fields(ModelProfile)}
        profiles = {
            name: ModelProfile(**{k: v for k, v in profile_data.items() if k in profile_fields})
            for name, profile_data in raw["models"]["profiles"].items()
        }
        models = ModelsConfig(
            default_profile=raw["models"]["default_profile"],
            profiles=profiles,
        )

        policy = PolicyConfig(
            default_action=raw["policy"]["default_action"],
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

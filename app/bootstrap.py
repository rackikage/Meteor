from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config import MeteorConfig

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "config" / "meteor.yaml"


@dataclass
class BootstrapResult:
    config: MeteorConfig
    repo_root: Path
    default_model_path: Path
    ready: bool
    warnings: list[str]


def _derive_repo_root(config_path: Path) -> Path:
    resolved_config_path = config_path.resolve(strict=False)
    if resolved_config_path.parent.name == "config":
        return resolved_config_path.parent.parent
    return resolved_config_path.parent


def resolve_repo_path(repo_root: Path, configured_path: str) -> Path:
    path = Path(configured_path)
    if path.is_absolute():
        return path.resolve(strict=False)
    return (repo_root / path).resolve(strict=False)


def bootstrap(config_path: Path = CONFIG_PATH) -> BootstrapResult:
    warnings: list[str] = []

    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    config = MeteorConfig.load(config_path)
    repo_root = _derive_repo_root(config_path)

    default_profile_name = config.models.default_profile
    default_profile = config.models.profiles.get(default_profile_name)
    if default_profile is None:
        raise ValueError(f"Default model profile '{default_profile_name}' not found in config.")

    model_path = resolve_repo_path(repo_root, default_profile.model_path)
    if not model_path.exists():
        warnings.append(f"Model file not found: {model_path}. Model execution will run disabled.")

    ready = len(warnings) == 0

    return BootstrapResult(
        config=config,
        repo_root=repo_root,
        default_model_path=model_path,
        ready=ready,
        warnings=warnings,
    )

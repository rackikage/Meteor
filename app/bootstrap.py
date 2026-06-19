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


def bootstrap(config_path: Path = CONFIG_PATH) -> BootstrapResult:
    warnings: list[str] = []

    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    config = MeteorConfig.load(config_path)
    runtime_base_dir = config_path.resolve(strict=False).parent

    default_profile_name = config.models.default_profile
    default_profile = config.models.profiles.get(default_profile_name)
    if default_profile is None:
        raise ValueError(f"Default model profile '{default_profile_name}' not found in config.")

    model_path = Path(default_profile.model_path)
    if not model_path.is_absolute():
        model_path = (runtime_base_dir / model_path).resolve(strict=False)
    if not model_path.exists():
        warnings.append(f"Model file not found: {model_path}. Runtime will not be able to execute inference.")

    ready = len(warnings) == 0

    return BootstrapResult(
        config=config,
        repo_root=REPO_ROOT,
        default_model_path=model_path,
        ready=ready,
        warnings=warnings,
    )

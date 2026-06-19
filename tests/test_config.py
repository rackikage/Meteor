from __future__ import annotations

from pathlib import Path

import pytest

from app.config import MeteorConfig

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "meteor.yaml"


def test_config_loads_successfully() -> None:
    config = MeteorConfig.load(CONFIG_PATH)
    assert config.app.name == "Meteor"


def test_config_local_first_is_true() -> None:
    config = MeteorConfig.load(CONFIG_PATH)
    assert config.app.local_first is True


def test_config_default_model_profile_exists() -> None:
    config = MeteorConfig.load(CONFIG_PATH)
    assert config.models.default_profile in config.models.profiles


def test_config_policy_default_action_is_deny() -> None:
    config = MeteorConfig.load(CONFIG_PATH)
    assert config.policy.default_action == "deny"


def test_config_policy_has_allow_rules() -> None:
    config = MeteorConfig.load(CONFIG_PATH)
    assert len(config.policy.allow_rules) > 0


def test_config_model_profile_has_required_fields() -> None:
    config = MeteorConfig.load(CONFIG_PATH)
    profile = config.models.profiles[config.models.default_profile]
    assert profile.backend == "llama_cpp"
    assert profile.model_path.endswith(".gguf")
    assert isinstance(profile.context_window, int)
    assert profile.wired is False

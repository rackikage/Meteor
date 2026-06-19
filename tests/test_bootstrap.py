from __future__ import annotations

from pathlib import Path

from app.bootstrap import bootstrap

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "meteor.yaml"


def test_bootstrap_returns_result() -> None:
    result = bootstrap(CONFIG_PATH)
    assert result is not None


def test_bootstrap_config_app_name() -> None:
    result = bootstrap(CONFIG_PATH)
    assert result.config.app.name == "Meteor"


def test_bootstrap_repo_root_exists() -> None:
    result = bootstrap(CONFIG_PATH)
    assert result.repo_root.exists()


def test_bootstrap_model_path_is_resolved() -> None:
    result = bootstrap(CONFIG_PATH)
    assert result.default_model_path.suffix == ".gguf"


def test_bootstrap_warning_if_gguf_missing(tmp_path) -> None:
    import shutil
    import yaml

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_file = config_dir / "meteor.yaml"

    base_config_path = Path(__file__).resolve().parent.parent / "config" / "meteor.yaml"
    with open(base_config_path) as f:
        raw = yaml.safe_load(f)

    raw["models"]["profiles"][raw["models"]["default_profile"]]["model_path"] = "nonexistent.gguf"
    with open(config_file, "w") as f:
        yaml.dump(raw, f)

    result = bootstrap(config_file)
    assert result.ready is False
    assert any("nonexistent.gguf" in w for w in result.warnings)

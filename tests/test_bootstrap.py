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
    assert result.default_model_path.suffix in (".gguf", "") or result.default_model_path.name == "llama3.2"


def test_bootstrap_uses_supplied_config_base_dir(tmp_path) -> None:
    import yaml

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_path = config_dir / "meteor.yaml"

    base_config_path = Path(__file__).resolve().parent.parent / "config" / "meteor.yaml"
    with open(base_config_path) as f:
        raw = yaml.safe_load(f)

    with open(config_path, "w") as f:
        yaml.safe_dump(raw, f)

    result = bootstrap(config_path)
    assert result.config.app.name == "Meteor"


def test_bootstrap_warning_if_gguf_missing(tmp_path) -> None:
    """A missing llama.cpp model_path should surface as a warning and mark the
    bootstrap not-ready. Hosted backends (Pollinations, Groq, …) use model_path
    as a remote id and are not filesystem-checked."""
    import yaml

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_file = config_dir / "meteor.yaml"

    base_config_path = Path(__file__).resolve().parent.parent / "config" / "meteor.yaml"
    with open(base_config_path) as f:
        raw = yaml.safe_load(f)

    # Force the default onto a llama.cpp profile pointing at a missing gguf.
    raw["models"]["default_profile"] = "llama3.2-3b-local"
    raw["models"]["profiles"]["llama3.2-3b-local"] = {
        "backend": "llama_cpp",
        "model_path": "nonexistent.gguf",
        "context_window": 4096,
        "temperature": 0.7,
        "temperature_structured": 0.2,
        "temperature_creative": 0.8,
        "max_tokens": 512,
        "wired": True,
    }
    with open(config_file, "w") as f:
        yaml.dump(raw, f)

    result = bootstrap(config_file)
    assert result.ready is False
    assert any("nonexistent.gguf" in w for w in result.warnings)

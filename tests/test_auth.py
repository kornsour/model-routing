import pytest

from model_routing.auth import AuthConfig, parse_auth
from model_routing.config import load_config

BASE = {"PATH": "/bin", "ANTHROPIC_API_KEY": "sk-a", "OPENAI_API_KEY": "sk-o"}


def test_subscription_scrubs_api_keys():
    env = AuthConfig().child_env("claude_cli", BASE)
    assert env == {"PATH": "/bin"}


def test_api_key_maps_to_cli_var():
    env = AuthConfig("api_key").child_env("codex_cli", BASE)
    assert env is not None
    assert env["CODEX_API_KEY"] == "sk-o" and "OPENAI_API_KEY" not in env
    env = AuthConfig("api_key").child_env("claude_cli", BASE)
    assert env is not None and env["ANTHROPIC_API_KEY"] == "sk-a"


def test_api_key_missing_raises():
    with pytest.raises(ValueError, match="MY_KEY"):
        AuthConfig("api_key", "MY_KEY").child_env("claude_cli", BASE)


def test_fake_provider_has_no_env():
    assert AuthConfig("api_key").child_env("fake", BASE) is None


def test_bad_mode_rejected():
    with pytest.raises(ValueError):
        AuthConfig("oauth")


def test_parse_auth_override():
    a = parse_auth({"mode": "subscription", "codex_cli": {"mode": "api_key"}})
    assert a["*"].mode == "subscription" and a["codex_cli"].mode == "api_key"


def test_load_config_auth(tmp_path):
    (tmp_path / "pyproject.toml").write_text("")
    p = tmp_path / "e.toml"
    p.write_text(
        '[experiment]\nname="x"\ntasks="t.jsonl"\n[auth]\nmode="api_key"\n'
        '[candidates.a]\nprovider="fake"\nmodel="m"\n'
    )
    cfg = load_config(p)
    assert cfg.auth_for("claude_cli").mode == "api_key"

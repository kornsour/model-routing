"""Hidden grader: layered ledger configuration (exp06 stratum B)."""

from datetime import UTC, datetime

import pytest

from toolbelt.iniconf import ConfigError, merge, parse

from ledger import cli, store
from ledger.config import load_config


# ------------------------------------------------------------------ toolbelt
def test_set_and_raw():
    c = parse("[a]\nx = 1\n[b : a]\ny = ${x}\n")
    c.set("b", "Z", "3")
    assert c.get("b", "z") == "3"
    c.set("new", "k", "v")
    assert c.get("new", "k") == "v"
    assert c.raw("b", "x") == ("1", "a")
    assert c.raw("b", "y") == ("${x}", "b")
    assert c.raw("b", "missing") is None


def test_merge():
    system = parse("[DEFAULT]\nregion = us\n[db]\nhost = sys-host\nuser = app\n[replica : db]\nhost = r1\n")
    project = parse("[db]\nhost = proj-host\nurl = ${user}@${host}/${region}\n[replica : other]\n[other]\nport = 5\n")
    merged = merge(system, project)
    assert merged.get("db", "host") == "proj-host"
    assert merged.get("db", "url") == "app@proj-host/us"
    assert merged.get("replica", "port") == "5"
    assert merged.get("replica", "host") == "r1"
    assert system.get("db", "host") == "sys-host" and not system.has_section("other")
    over = parse("[DEFAULT]\nregion = eu\n")
    assert merge(system, project, over).get("db", "url") == "app@proj-host/eu"


# ------------------------------------------------------------------ ledger.config
@pytest.fixture
def files(tmp_path):
    system = tmp_path / "system.ini"
    system.write_text(
        "[db]\npassword = hunter2\nuser = app\ndsn = postgres://${user}:${password}@h/db\n"
        "[api]\ntoken = abc\nurl = https://x/${api_path}\napi_path = v1\n"
        "[svc]\nconn = ${db:dsn}?x=1\n"
    )
    project = tmp_path / "project.ini"
    project.write_text("[paths]\nhistory = proj-history.jsonl\n[db_replica : db]\nhost = r1\n")
    return system, project


def test_layers_and_provenance(files):
    system, project = files
    env = {"LEDGER__PATHS__INFLIGHT": "env-inflight.json", "LEDGER_PATHS_RATES": "ignored", "OTHER": "x",
           "LEDGER__DB__USER": "svc"}
    cfg = load_config(system=system, project=project, env=env, overrides=["paths.rates=cli-rates.json"])
    assert cfg.get("paths", "history") == "proj-history.jsonl"
    assert cfg.provenance("paths", "history") == f"project:{project}"
    assert cfg.get("paths", "inflight") == "env-inflight.json"
    assert cfg.provenance("paths", "inflight") == "env:LEDGER__PATHS__INFLIGHT"
    assert cfg.get("paths", "rates") == "cli-rates.json"
    assert cfg.provenance("paths", "rates") == "cli:paths.rates"
    assert cfg.provenance("db", "password") == f"system:{system}"
    assert cfg.get("db", "dsn") == "postgres://svc:hunter2@h/db"
    assert cfg.provenance("db", "user") == "env:LEDGER__DB__USER"
    assert cfg.provenance("db_replica", "password") == f"system:{system}"
    assert cfg.provenance("db_replica", "host") == f"project:{project}"
    defaults = load_config(env={})
    assert defaults.get("paths", "history") == "history.jsonl" and defaults.provenance("paths", "history") == "default"


@pytest.mark.parametrize("bad", ["paths.history", "nohistory=x", "=x", ".k=v"])
def test_bad_overrides(bad):
    with pytest.raises(ValueError):
        load_config(env={}, overrides=[bad])


def test_dump_redacts_secrets_and_derived_values(files):
    system, _ = files
    cfg = load_config(system=system, env={})
    s = f"system:{system}"
    assert cfg.dump() == (
        "[api]\n"
        f"api_path = v1  # {s}\n"
        f"token = ********  # {s}\n"
        f"url = https://x/v1  # {s}\n"
        "\n"
        "[db]\n"
        f"dsn = postgres://${{user}}:${{password}}@h/db  # {s}\n"
        f"password = ********  # {s}\n"
        f"user = app  # {s}\n"
        "\n"
        "[paths]\n"
        "history = history.jsonl  # default\n"
        "inflight = inflight.json  # default\n"
        "rates = rates.json  # default\n"
        "\n"
        "[svc]\n"
        f"conn = ${{db:dsn}}?x=1  # {s}\n"
    )
    assert "hunter2" not in cfg.dump() and "abc" not in cfg.dump()


def test_secret_key_names(tmp_path):
    p = tmp_path / "s.ini"
    p.write_text("[x]\napi_key = k1\nmonkey = m\nkeyring = r\nSecretThing = s\nmy_token_path = t\n")
    dump = load_config(system=p, env={}).dump()
    assert "api_key = ********" in dump and "monkey = ********" in dump
    assert "keyring = r" in dump
    assert "secretthing = ********" in dump.lower() and "my_token_path = ********" in dump


def test_fails_loudly(tmp_path):
    p = tmp_path / "p.ini"
    p.write_text("[a]\nx = ${nope}\n")
    with pytest.raises(ConfigError, match="nope"):
        load_config(project=p, env={})
    p.write_text("[a]\nx = ${y}\ny = ${x}\n")
    with pytest.raises(ConfigError):
        load_config(project=p, env={})


# ------------------------------------------------------------------ CLI
def test_cli_uses_config_paths(tmp_path, capsys, files, monkeypatch):
    system, project = files
    history = tmp_path / "h.jsonl"
    store.append(history, store.RunRecord("r1", "nightly", datetime(2026, 9, 2, tzinfo=UTC), "success", 3.0, {"j": 3.0}))
    monkeypatch.chdir(tmp_path)
    assert cli.main(["--set", f"paths.history={history}", "report", "--month", "2026-09"]) == 0
    assert "nightly" in capsys.readouterr().out
    assert cli.main(["--system-config", str(system), "--config", str(project), "config", "why", "paths.history"]) == 0
    assert capsys.readouterr().out.strip() == f"project:{project}"
    assert cli.main(["--system-config", str(system), "config", "get", "db.password"]) == 0
    assert capsys.readouterr().out.strip() == "********"
    assert cli.main(["--system-config", str(system), "config", "get", "api.url"]) == 0
    assert capsys.readouterr().out.strip() == "https://x/v1"
    assert cli.main(["config", "get", "nope.key"]) == 1
    assert capsys.readouterr().err.strip()
    assert cli.main(["--system-config", str(system), "config", "show"]) == 0
    assert "token = ********" in capsys.readouterr().out
    assert cli.main(["report", "--month", "2026-09", "--history", str(history)]) == 0


def test_default_project_file_in_cwd(tmp_path, monkeypatch):
    (tmp_path / "ledger.ini").write_text("[paths]\nhistory = cwd.jsonl\n")
    monkeypatch.chdir(tmp_path)
    cfg = load_config(env={})
    assert cfg.get("paths", "history") == "cwd.jsonl"
    assert cfg.provenance("paths", "history").startswith("project:")


def test_parent_from_another_layer():
    with pytest.raises(ConfigError):
        parse("[child : base]\nx = 1\n")
    child = parse("[child : base]\nx = 1\n", require_parents=False)
    merged = merge(parse("[base]\ny = 2\n"), child)
    assert merged.get("child", "y") == "2"
    with pytest.raises(ConfigError):
        merge(child)

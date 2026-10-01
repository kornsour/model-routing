from ledger.config import load_config


def test_env_beats_project(tmp_path):
    p = tmp_path / "p.ini"
    p.write_text("[paths]\nhistory = p.jsonl\n")
    cfg = load_config(project=p, env={"LEDGER__PATHS__HISTORY": "e.jsonl"})
    assert cfg.get("paths", "history") == "e.jsonl"
    assert cfg.provenance("paths", "history") == "env:LEDGER__PATHS__HISTORY"


def test_secret_never_dumped(tmp_path):
    p = tmp_path / "p.ini"
    p.write_text("[db]\npassword = pw\nurl = x:${password}\n")
    dump = load_config(project=p, env={}).dump()
    assert "pw" not in dump.replace("password", "")

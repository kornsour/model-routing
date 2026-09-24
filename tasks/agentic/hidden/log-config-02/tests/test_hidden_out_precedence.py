from pathlib import Path

import pytest
from logproc.cli import main

LOG = "2024-03-01T10:00:00 INFO started\n2024-03-01T10:00:01 ERROR boom\n"


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A project dir with logproc.toml, a nested working dir, and no LOGPROC_OUT."""
    root = tmp_path / "proj"
    sub = root / "svc" / "logs"
    sub.mkdir(parents=True)
    (root / "logproc.toml").write_text('[output]\npath = "out/entries.csv"\n')
    (root / "out").mkdir()
    log = sub / "app.log"
    log.write_text(LOG)
    monkeypatch.delenv("LOGPROC_OUT", raising=False)
    monkeypatch.chdir(sub)
    return root, sub, log


def _csv_files(*dirs: Path) -> set[Path]:
    return {p for d in dirs for p in d.rglob("*.csv")}


# README rule 3: with no flag and no env, the nearest logproc.toml decides, and a relative path
# is relative to the toml's directory, "from any subdirectory of a project".
def test_toml_path_is_relative_to_toml_dir_from_subdirectory(project):
    root, sub, log = project
    assert main(["process", str(log)]) == 0
    assert (root / "out" / "entries.csv").is_file()
    assert _csv_files(root) == {root / "out" / "entries.csv"}


# README rule 1: "--out PATH on the command line" beats env and toml.
def test_flag_wins_over_env_and_toml(project, monkeypatch, tmp_path):
    root, sub, log = project
    monkeypatch.setenv("LOGPROC_OUT", str(tmp_path / "env.csv"))
    target = tmp_path / "flag.csv"
    assert main(["process", str(log), "--out", str(target)]) == 0
    assert target.is_file()
    assert _csv_files(root, tmp_path) == {target}


# README rule 2: a non-empty LOGPROC_OUT beats the toml.
def test_env_wins_over_toml(project, monkeypatch, tmp_path):
    root, sub, log = project
    target = tmp_path / "env.csv"
    monkeypatch.setenv("LOGPROC_OUT", str(target))
    assert main(["process", str(log)]) == 0
    assert target.is_file()
    assert _csv_files(root, tmp_path) == {target}


# README rule 2: "An empty LOGPROC_OUT is the same as an unset one".
def test_empty_env_falls_through_to_toml(project, monkeypatch):
    root, sub, log = project
    monkeypatch.setenv("LOGPROC_OUT", "")
    assert main(["process", str(log)]) == 0
    assert _csv_files(root) == {root / "out" / "entries.csv"}


# README rule 4: "Otherwise entries.csv in the working directory".
def test_default_is_entries_csv_in_cwd(tmp_path, monkeypatch):
    work = tmp_path / "plain"
    work.mkdir()
    log = work / "app.log"
    log.write_text(LOG)
    monkeypatch.delenv("LOGPROC_OUT", raising=False)
    monkeypatch.chdir(work)
    assert main(["process", str(log)]) == 0
    assert (work / "entries.csv").is_file()


# README rule 1 with a relative --out: the flag is taken as given (relative to the working
# directory, as any command-line path would be), not re-based onto the toml directory.
def test_relative_flag_is_relative_to_cwd(project):
    root, sub, log = project
    assert main(["process", str(log), "--out", "here.csv"]) == 0
    assert (sub / "here.csv").is_file()
    assert _csv_files(root) == {sub / "here.csv"}

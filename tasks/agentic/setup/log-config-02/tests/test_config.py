from logproc.config import find_config, load_config


def test_find_config_walks_up(tmp_path):
    (tmp_path / "logproc.toml").write_text('[output]\npath = "out/entries.csv"\n')
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    assert find_config(nested) == tmp_path / "logproc.toml"
    assert find_config(tmp_path) == tmp_path / "logproc.toml"


def test_load_config_reads_output_path(tmp_path):
    (tmp_path / "logproc.toml").write_text('[output]\npath = "out/entries.csv"\n')
    config = load_config(tmp_path)
    assert config.path == tmp_path / "logproc.toml"
    assert config.out is not None
    assert config.out.endswith("out/entries.csv")


def test_load_config_without_file(tmp_path):
    config = load_config(tmp_path)
    assert config.path is None
    assert config.out is None

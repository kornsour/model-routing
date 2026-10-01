from toolbelt.iniconf import parse

TEXT = """
[DEFAULT]
region = eu-west-1

[api]
host = api.internal
port = 8080
url = https://${host}:${port}
debug = yes
"""


def test_basic():
    cfg = parse(TEXT)
    assert cfg.sections() == ["api"]
    assert cfg.get("api", "url") == "https://api.internal:8080"
    assert cfg.getint("api", "port") == 8080
    assert cfg.getbool("api", "debug") is True
    assert cfg.get("api", "region") == "eu-west-1"

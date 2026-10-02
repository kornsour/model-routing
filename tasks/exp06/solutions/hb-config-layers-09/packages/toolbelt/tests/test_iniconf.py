import pytest

from toolbelt.iniconf import ConfigError, parse

TEXT = """
# services.ini
; old-style comment
[DEFAULT]
region = eu-west-1
Log_Level = info
home = /srv/${name}

[base]
name = base
timeout = 30
retries: 3
tags = a, b, ,c
url = https://${host}:${port}/  # trailing comment
host = base.internal
port = 80

[api : base]
name = api
port = 8443
path = ${url}v1
price = $$5 per ${base:name}
motd = "Hello; world # not a comment"
escaped = "tab\\there \\"quoted\\" back\\\\slash"
hosts =
    one.internal
    two.internal   # second
    three.internal
enabled = On
ratio = 0.25
weird = a#b;c
dollar = "cost: $$3"

[worker:api]
name = worker
queue = ${api:name}-${name}
"""


@pytest.fixture
def cfg():
    return parse(TEXT)


def test_sections_and_keys(cfg):
    assert cfg.sections() == ["base", "api", "worker"]
    assert cfg.has_section("api") and not cfg.has_section("DEFAULT")
    assert cfg.keys("base") == ["name", "timeout", "retries", "tags", "url", "host", "port", "region", "log_level", "home"]
    ks = cfg.keys("worker")
    assert ks[:2] == ["name", "queue"]
    assert ks.index("port") < ks.index("timeout") < ks.index("region")
    assert len(ks) == len(set(ks))


def test_inheritance_and_default(cfg):
    assert cfg.get("api", "timeout") == "30"
    assert cfg.getint("worker", "retries") == 3
    assert cfg.get("worker", "region") == "eu-west-1"
    assert cfg.get("api", "LOG_LEVEL") == "info"
    assert cfg.get("worker", "Log_level") == "info"


def test_interpolation_uses_requesting_section(cfg):
    assert cfg.get("base", "url") == "https://base.internal:80/"
    assert cfg.get("api", "url") == "https://base.internal:8443/"
    assert cfg.get("api", "path") == "https://base.internal:8443/v1"
    assert cfg.get("worker", "home") == "/srv/worker"
    assert cfg.get("base", "home") == "/srv/base"
    assert cfg.get("worker", "queue") == "api-worker"
    assert cfg.get("api", "price") == "$5 per base"
    assert cfg.get("api", "dollar") == "cost: $3"


def test_quoting_and_comments(cfg):
    assert cfg.get("api", "motd") == "Hello; world # not a comment"
    assert cfg.get("api", "escaped") == 'tab\there "quoted" back\\slash'
    assert cfg.get("api", "weird") == "a#b;c"


def test_continuation_and_lists(cfg):
    assert cfg.get("api", "hosts") == "\none.internal\ntwo.internal\nthree.internal"
    assert cfg.getlist("api", "hosts") == ["one.internal", "two.internal", "three.internal"]
    assert cfg.getlist("base", "tags") == ["a", "b", "c"]


def test_typed_getters(cfg):
    assert cfg.getbool("api", "enabled") is True
    assert cfg.getfloat("api", "ratio") == 0.25
    with pytest.raises(ValueError):
        cfg.getbool("api", "name")
    with pytest.raises(ValueError):
        cfg.getint("api", "name")


def test_defaults_for_missing(cfg):
    assert cfg.get("api", "nope", "fallback") == "fallback"
    assert cfg.get("nosuch", "x", None) is None
    assert cfg.getint("api", "nope", 7) == 7
    assert cfg.getbool("api", "nope", False) is False
    assert cfg.getlist("api", "nope", []) == []
    with pytest.raises(ConfigError):
        cfg.get("api", "nope")
    with pytest.raises(ConfigError):
        cfg.get("nosuch", "x")


def test_error_types():
    assert issubclass(ConfigError, ValueError)


@pytest.mark.parametrize(
    "text,key",
    [
        ("[a]\nx = ${y}\ny = ${x}\n", ("a", "x")),
        ("[a]\nx = ${x}\n", ("a", "x")),
        ("[a]\nx = ${b:y}\n[b]\ny = ${a:x}\n", ("a", "x")),
        ("[a]\nx = ${missing}\n", ("a", "x")),
        ("[a]\nx = ${nosection:y}\n", ("a", "x")),
        ("[a]\nx = $y\n", ("a", "x")),
        ("[a]\nx = ${y\ny = 1\n", ("a", "x")),
        ("[a]\nx = ${}\n", ("a", "x")),
    ],
)
def test_interpolation_errors(text, key):
    cfg = parse(text)
    with pytest.raises(ConfigError):
        cfg.get(*key)


def test_cycle_message_names_the_path():
    cfg = parse("[a]\nx = ${y}\ny = ${z}\nz = ${x}\n")
    with pytest.raises(ConfigError, match="cycle"):
        cfg.get("a", "x")


def test_deep_but_acyclic_chain_is_fine():
    lines = ["[a]"] + [f"k{i} = ${{k{i + 1}}}x" for i in range(300)] + ["k300 = end"]
    cfg = parse("\n".join(lines))
    assert cfg.get("a", "k0") == "end" + "x" * 300


@pytest.mark.parametrize(
    "text,lineno",
    [
        ("x = 1\n", 1),
        ("[a]\nx = 1\nX = 2\n", 3),
        ("[a]\n[a]\n", 2),
        ("[a]\njust text\n", 2),
        ("[a\nx=1\n", 1),
        ('[a]\nx = "unterminated\n', 2),
        ('[a]\nx = "bad \\q escape"\n', 2),
        ('[a]\nx = "a" b\n', 2),
    ],
)
def test_parse_errors_have_line_numbers(text, lineno):
    with pytest.raises(ConfigError) as exc:
        parse(text)
    assert exc.value.lineno == lineno


@pytest.mark.parametrize(
    "text",
    [
        "[a : b]\nx = 1\n",
        "[a : b]\n[b : a]\n",
        "[a : a]\n",
        "[a : b]\n[b : c]\n[c : a]\n",
        "[DEFAULT : a]\n[a]\n",
    ],
)
def test_inheritance_errors(text):
    with pytest.raises(ConfigError):
        parse(text)


def test_blank_line_then_indented_text_is_an_error():
    with pytest.raises(ConfigError):
        parse("[a]\nx = 1\n\n  just text\n")


def test_section_names_case_sensitive_keys_not():
    cfg = parse("[App]\nKey = v\n[app]\nkey = w\n")
    assert cfg.get("App", "KEY") == "v"
    assert cfg.get("app", "key") == "w"


def test_set_raw_and_merge():
    from toolbelt.iniconf import merge

    base = parse("[db]\nhost = a\nuser = u\n")
    top = parse("[db]\nhost = b\nurl = ${user}@${host}\n")
    merged = merge(base, top)
    assert merged.get("db", "url") == "u@b"
    assert base.get("db", "host") == "a"
    merged.set("db", "Port", "5")
    assert merged.raw("db", "port") == ("5", "db")

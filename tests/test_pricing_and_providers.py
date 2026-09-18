import json

from model_routing.pricing import PriceTable
from model_routing.providers.claude_cli import ClaudeCliProvider, parse_result
from model_routing.providers.codex_cli import CodexCliProvider, parse_jsonl
from model_routing.types import Usage


def test_price_table_aliases_and_cache_rates():
    t = PriceTable.load()
    haiku = t.get("haiku")
    assert haiku is not None and haiku.model == "claude-haiku-4-5"
    assert t.get("claude-haiku-4-5-20251001") is haiku
    u = Usage(
        input_tokens=1_000_000, cache_read=1_000_000, cache_write=1_000_000, output_tokens=1_000_000
    )
    assert t.cost("haiku", u) == 1.0 + 0.10 + 1.25 + 5.0
    assert t.cost("gpt-5.6-luna", Usage(input_tokens=1_000_000)) == 0.20


def test_price_table_rejects_unknown_model():
    t = PriceTable.load()
    try:
        t.cost("nope", Usage())
    except ValueError as e:
        assert "pricing.toml" in str(e)
    else:
        raise AssertionError("expected ValueError")


CLAUDE_RESULT = {
    "duration_api_ms": 813,
    "stop_reason": "end_turn",
    "total_cost_usd": 0.000846,
    "usage": {
        "input_tokens": 621,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "output_tokens": 45,
        "output_tokens_details": {"thinking_tokens": 38},
    },
    "modelUsage": {
        "claude-haiku-4-5-20251001": {"canonicalModel": "claude-haiku-4-5", "costUSD": 0.000846}
    },
    "is_error": False,
    "result": "OK",
    "duration_ms": 1988,
    "structured_output": {"difficulty": "easy"},
}


def test_parse_claude_result_maps_usage_cost_and_structured():
    r = parse_result(CLAUDE_RESULT, wall_ms=2000)
    assert r.output == "OK" and r.error is None
    assert r.usage.input_tokens == 621 and r.usage.reasoning == 38
    assert r.resolved_model == "claude-haiku-4-5"
    assert r.cost_usd_reported is not None and r.cost_usd_reported == 0.000846
    assert r.structured == {"difficulty": "easy"}
    # Cross-check: list price from the table agrees with the CLI's reported cost.
    assert abs(PriceTable.load().cost(r.resolved_model, r.usage) - r.cost_usd_reported) < 1e-9


def test_one_hour_ttl_cache_writes_match_cli_reported_cost():
    # Real `claude -p` sonnet call on 2026-09-18 with a ~2.9k-token system prompt:
    # the CLI wrote the whole prefix with the 1-hour TTL and reported $0.01148.
    data = {
        "total_cost_usd": 0.01148,
        "usage": {
            "input_tokens": 2,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 2859,
            "cache_creation": {"ephemeral_1h_input_tokens": 2859, "ephemeral_5m_input_tokens": 0},
            "output_tokens": 4,
        },
        "modelUsage": {"claude-sonnet-5": {"canonicalModel": "claude-sonnet-5"}},
        "result": "OK",
    }
    r = parse_result(data, wall_ms=1)
    assert r.usage.cache_write_1h == 2859
    assert abs(PriceTable.load().cost("claude-sonnet-5", r.usage) - 0.01148) < 1e-9
    # Priced as a 5-minute write it would be ~37% less - the naive figure.
    naive = PriceTable.load().cost("claude-sonnet-5", Usage(2, 0, 2859, 4))
    assert naive < 0.0075


def test_parse_claude_error_result():
    r = parse_result({"is_error": True, "result": "Not logged in", "usage": {}}, wall_ms=5)
    assert r.error and "Not logged in" in r.error


def test_claude_args_are_minimal_and_reproducible():
    args = ClaudeCliProvider().build_args(
        "sonnet", "hi", system="ctx", effort="low", schema={"type": "object"}, extra=None
    )
    assert "--bare" not in args  # --bare disables OAuth; the harness relies on the login
    for flag in ("--tools", "--setting-sources", "--strict-mcp-config", "--no-session-persistence"):
        assert flag in args
    assert args[args.index("--tools") + 1] == ""
    assert args[args.index("--effort") + 1] == "low"
    assert json.loads(args[args.index("--json-schema") + 1]) == {"type": "object"}


CODEX_STDOUT = "\n".join(
    [
        "Reading additional input from stdin...",
        '{"type":"thread.started","thread_id":"t1"}',
        '{"type":"turn.started"}',
        '{"type":"item.completed","item":{"id":"item_0","type":"error",'
        '"message":"Skill descriptions were shortened"}}',
        '{"type":"item.completed","item":{"id":"item_1","type":"agent_message","text":"OK"}}',
        '{"type":"turn.completed","usage":{"input_tokens":17971,"cached_input_tokens":10624,'
        '"cache_write_input_tokens":0,"output_tokens":5,"reasoning_output_tokens":0}}',
    ]
)


def test_parse_codex_jsonl_normalizes_cached_input():
    r = parse_jsonl(CODEX_STDOUT, wall_ms=4950)
    assert r.output == "OK" and r.error is None
    # Codex's input_tokens includes the cached portion; Usage keeps them disjoint.
    assert r.usage.input_tokens == 17971 - 10624
    assert r.usage.cache_read == 10624
    assert r.usage.prompt_tokens == 17971


def test_codex_args_prepend_context_and_ignore_user_config():
    args = CodexCliProvider().build_args(
        "gpt-5.6-luna",
        "question",
        system="the handbook",
        effort="low",
        schema_path=None,
        extra=None,
    )
    assert "--ignore-user-config" in args and "--ephemeral" in args
    assert args[-1].startswith("<context>\nthe handbook\n</context>")
    assert 'model_reasoning_effort="low"' in args

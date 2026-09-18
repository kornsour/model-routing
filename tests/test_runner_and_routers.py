import json
from pathlib import Path

from model_routing.cli import main
from model_routing.config import load_config
from model_routing.pricing import PriceTable
from model_routing.providers.fake import FakeProvider
from model_routing.report import aggregate, load_outcomes, pareto, write_report
from model_routing.routers import make_router
from model_routing.runner import Runner
from model_routing.tasks import load_tasks
from model_routing.types import Task

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "tasks" / "llm" / "knowledge_work.jsonl"


def test_task_set_loads_and_labels_are_valid():
    tasks = load_tasks(TASKS)
    assert len(tasks) >= 30
    assert {t.difficulty for t in tasks} == {"easy", "medium", "hard"}
    ctx = [t for t in tasks if t.context]
    assert len(ctx) >= 10
    handbook = (TASKS.parent / "context" / "handbook.md").read_text()
    # Longer than Haiku 4.5's 4096-token minimum cacheable prefix (~4 chars/token).
    assert len(handbook) > 4096 * 4


def test_sample_and_tags_selection():
    ctx = load_tasks(TASKS, tags=["context"])
    assert ctx and all(t.context for t in ctx)
    picked = load_tasks(TASKS, sample=6)
    assert len(picked) == 6 and len({t.id for t in picked}) == 6
    assert {t.difficulty for t in picked} == {"easy", "medium", "hard"}
    assert any(t.context for t in picked) and any(not t.context for t in picked)
    assert load_tasks(TASKS, sample=1000) == load_tasks(TASKS)


def test_every_experiment_config_validates():
    prices = PriceTable.load()
    for path in sorted((ROOT / "experiments" / "llm").glob("*.toml")):
        cfg = load_config(path)
        assert cfg.tasks.exists(), path
        for c in cfg.candidates.values():
            assert prices.get(c.model) is not None, f"{path}: no price for {c.model}"


def _write_config(tmp_path: Path, order: str = "by_router") -> Path:
    cfg = tmp_path / "exp.toml"
    cfg.write_text(
        f"""
[experiment]
name = "t"
tasks = "{TASKS}"
order = "{order}"

[candidates.cheap]
provider = "fake"
model = "haiku"

[candidates.strong]
provider = "fake"
model = "opus"

[[routers]]
name = "all_cheap"
kind = "static"
candidate = "cheap"

[[routers]]
name = "oracle"
kind = "oracle"
map = {{ easy = "cheap", medium = "cheap", hard = "strong", default = "cheap" }}

[[routers]]
name = "cascade"
kind = "cascade"
chain = ["cheap", "strong"]
escalate_on = "grader"

[[routers]]
name = "clf"
kind = "classifier"
classifier = "cheap"
map = {{ easy = "cheap", medium = "cheap", hard = "strong", default = "cheap" }}
"""
    )
    return cfg


def test_runner_end_to_end_with_fake_provider(tmp_path: Path):
    cfg = load_config(_write_config(tmp_path))
    tasks = load_tasks(TASKS, limit=6)
    # The "strong" fake knows the answers; the "cheap" fake does not.
    strong = FakeProvider(answers={t.prompt: _answer(t) for t in tasks})
    cheap = FakeProvider()

    class Split:
        name = "fake"

        def call(self, model, prompt, **kw):
            return (strong if model == "opus" else cheap).call(model, prompt, **kw)

    out = tmp_path / "run"
    runner = Runner(cfg, {"fake": Split()}, PriceTable.load(), out, limit=6, verbose=False)
    outcomes = runner.run()
    assert len(outcomes) == 4 * 6
    calls = [json.loads(line) for line in (out / "calls.jsonl").read_text().splitlines()]
    assert len(calls) == runner.seq
    by_router = {o.router: o for o in outcomes}
    assert by_router["cascade"].escalations in (0, 1)
    # Cascade escalates on every cheap failure and then passes via strong.
    cascade = [o for o in outcomes if o.router == "cascade"]
    assert all(o.passed for o in cascade)
    assert all(o.escalations == 1 for o in cascade)
    # Classifier router bills its routing call to the task.
    clf = [o for o in outcomes if o.router == "clf"]
    assert all(o.router_cost_usd > 0 for o in clf)

    md = write_report(out)
    stats = {s.router: s for s in aggregate(load_outcomes(out))}
    assert stats["cascade"].pass_rate == 1.0
    assert stats["all_cheap"].cost_per_pass is None  # zero passes -> undefined, not zero
    assert "cost/pass" in md and (out / "summary.csv").exists()
    front = pareto(list(stats.values()))
    assert "cascade" in front


def _answer(t: Task) -> str:
    g = t.grader
    if g["type"] == "number":
        return str(g["value"])
    if g["type"] == "exact":
        return g["value"]
    if g["type"] == "contains_all":
        return " ".join(g["values"])
    if g["type"] == "json_fields":
        return json.dumps(g["expect"])
    if g["type"] == "regex":
        return "2026-04-29 12:00 PM ET april 2"
    if g["type"] == "all_of":
        return " ".join(
            _answer(Task("x", "x", s)) for s in g["graders"] if s["type"] != "max_words"
        )
    return "?"


def test_fake_provider_models_model_scoped_cache():
    p = FakeProvider()
    system = "x" * 5000  # ~1250 tokens, above the cache minimum
    first = p.call("haiku", "q", system=system).usage
    second = p.call("haiku", "q", system=system).usage
    other = p.call("opus", "q", system=system).usage
    assert first.cache_write > 0 and first.cache_read == 0
    assert second.cache_read > 0 and second.cache_write == 0
    assert other.cache_write > 0  # a different model is a cold cache


def test_budget_stops_the_run(tmp_path: Path):
    cfg = load_config(_write_config(tmp_path))
    out = tmp_path / "run"
    runner = Runner(
        cfg, {"fake": FakeProvider()}, PriceTable.load(), out, budget_usd=0.01, verbose=False
    )
    outcomes = runner.run()
    assert 0 < len(outcomes) < 4 * len(load_tasks(TASKS))


def test_confidence_cascade_strips_suffix_before_grading():
    from model_routing.routers.strategies import strip_confidence

    assert strip_confidence("negative\n\nCONFIDENCE: high") == "negative"
    assert strip_confidence("**13488.50**\nCONFIDENCE: low") == "**13488.50**"
    assert strip_confidence("no suffix") == "no suffix"


def test_routers_filter_and_cooldown_plumbing(tmp_path: Path):
    cfg = load_config(_write_config(tmp_path))
    out = tmp_path / "run"
    runner = Runner(
        cfg,
        {"fake": FakeProvider()},
        PriceTable.load(),
        out,
        limit=2,
        routers_filter=("all_cheap",),
        verbose=False,
    )
    assert [r.name for r in runner.routers] == ["all_cheap"]
    assert len(runner.run()) == 2


def test_heuristic_router_labels():
    r = make_router(
        {
            "name": "h",
            "kind": "heuristic",
            "map": {"easy": "a", "medium": "b", "hard": "c", "default": "b"},
        }
    )
    assert r.label(Task("a", "Classify this as positive or negative.", {})) == "easy"
    assert (
        r.label(Task("b", "Reconcile these two lists and report every mismatch " * 3, {})) == "hard"
    )


def test_cli_estimate_and_fake_run(tmp_path: Path, capsys):
    cfg = _write_config(tmp_path)
    assert main(["estimate", str(cfg), "--limit", "3", "--out", str(tmp_path / "r")]) == 0
    assert "Estimated list-price cost" in capsys.readouterr().out
    assert main(["run", str(cfg), "--fake", "--limit", "2", "--out", str(tmp_path / "r")]) == 0
    assert "Pareto" in capsys.readouterr().out

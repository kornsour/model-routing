"""Hidden grader: exact money in ledger (exp06 stratum B)."""

import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from orchestra import JobSpec, run
from orchestra import store as run_store
from toolbelt.money import from_minor

from ledger import budget, cli, pricing, rates, report, store


# ------------------------------------------------------------------ toolbelt
def test_from_minor():
    assert from_minor(1234, "USD") == Decimal("12.34")
    assert from_minor(5, "JPY") == Decimal("5")
    assert from_minor(-1, "KWD") == Decimal("-0.001")
    with pytest.raises(TypeError):
        from_minor(1.0, "USD")
    with pytest.raises(TypeError):
        from_minor(True, "USD")
    with pytest.raises(ValueError):
        from_minor(1, "XXX")


# ------------------------------------------------------------------ rates
def test_default_rates_are_decimal():
    assert rates.DEFAULT_RATES["warehouse"] == Decimal("0.0004")
    assert all(isinstance(v, Decimal) for v in rates.DEFAULT_RATES.values())


def test_load_rates_reads_numbers_exactly(tmp_path):
    path = tmp_path / "rates.json"
    path.write_text('{"warehouse": 0.0004, "api": "0.00002", "cpu": 1}')
    loaded = rates.load_rates(path)
    assert loaded == {"warehouse": Decimal("0.0004"), "api": Decimal("0.00002"), "cpu": Decimal(1)}
    assert all(isinstance(v, Decimal) for v in loaded.values())


@pytest.mark.parametrize("bad", ['{"api": -0.1}', '{"api": "abc"}', '{"api": "NaN"}', '{"api": null}'])
def test_load_rates_rejects_bad_values(tmp_path, bad):
    path = tmp_path / "rates.json"
    path.write_text(bad)
    with pytest.raises(ValueError, match="api"):
        rates.load_rates(path)


# ------------------------------------------------------------------ pricing
RATES = {"warehouse": Decimal("0.0335"), "api": Decimal("0.25")}


def _three_jobs():
    specs = {n: JobSpec(n, duration=10, resources={"warehouse": 1}) for n in ("a", "b", "c")}
    return specs, run(specs.values(), {"warehouse": 3})


def test_costs_are_exact_decimals():
    specs, result = _three_jobs()
    cost = pricing.price_run(result, specs, RATES)
    assert all(isinstance(a.cost, Decimal) for a in cost.attempts)
    assert cost.by_job == {"a": Decimal("0.335"), "b": Decimal("0.335"), "c": Decimal("0.335")}
    assert cost.total == Decimal("1.005")


def test_minor_allocation_sums_to_total():
    specs, result = _three_jobs()
    total, jobs = pricing.price_run(result, specs, RATES).minor()
    assert total == 100  # 100.5 cents rounds half-even
    assert jobs == {"a": 34, "b": 33, "c": 33}


def test_minor_with_fractional_times_and_retries():
    specs = {
        "x": JobSpec("x", duration=0.25, outcomes=("fail", "ok"), max_attempts=2, backoff=0.5, resources={"api": 3}),
        "y": JobSpec("y", deps=("x",), duration=0.75, resources={"warehouse": 2}),
        "z": JobSpec("z", duration=0.3),
    }
    cost = pricing.price_run(run(specs.values(), {"api": 3, "warehouse": 2}), specs, RATES)
    assert cost.by_job == {"x": Decimal("0.375"), "y": Decimal("0.05025"), "z": Decimal(0)}
    assert cost.minor() == (43, {"x": 38, "y": 5, "z": 0})


def test_minor_all_zero():
    specs = {"z": JobSpec("z", duration=5)}
    assert pricing.price_run(run(specs.values()), specs, RATES).minor() == (0, {"z": 0})


# ------------------------------------------------------------------ store
T = datetime(2026, 9, 3, 2, tzinfo=UTC)


def test_record_v2_round_trip(tmp_path):
    rec = store.RunRecord("r1", "nightly", T, "success", 1005, {"a": 500, "b": 505})
    assert rec.currency == "USD" and rec.total_usd == Decimal("10.05")
    path = tmp_path / "h.jsonl"
    store.append(path, rec)
    doc = json.loads(path.read_text())
    assert doc == {
        "version": 2, "run_id": "r1", "pipeline": "nightly", "started_at": "2026-09-03T02:00:00+00:00",
        "status": "success", "currency": "USD", "total_minor": 1005, "jobs_minor": {"a": 500, "b": 505},
    }
    assert store.load(path) == [rec]


def test_record_parts_must_sum():
    with pytest.raises(ValueError):
        store.RunRecord("r1", "nightly", T, "success", 1005, {"a": 500, "b": 500})


def test_mixed_v1_v2_history(tmp_path):
    path = tmp_path / "h.jsonl"
    v1 = {"version": 1, "run_id": "old", "pipeline": "nightly", "started_at": "2026-09-01T02:00:00+00:00",
          "status": "success", "total_usd": 1.005, "jobs": {"c": 0.335, "a": 0.335, "b": 0.335}}
    v1_empty = {"version": 1, "run_id": "old2", "pipeline": "hourly", "started_at": "2026-09-01T03:00:00+00:00",
                "status": "failed", "total_usd": 0.0, "jobs": {}}
    path.write_text(json.dumps(v1) + "\n" + json.dumps(v1_empty) + "\n")
    store.append(path, store.RunRecord("new", "nightly", T, "success", 7, {"a": 7}))
    loaded = {r.run_id: r for r in store.load(path)}
    assert loaded["old"].total_minor == 100 and loaded["old"].jobs_minor == {"a": 34, "b": 33, "c": 33}
    assert loaded["old2"].total_minor == 0 and loaded["old2"].jobs_minor == {}
    assert loaded["new"].total_minor == 7
    assert path.read_text().splitlines()[0] == json.dumps(v1), "existing lines must not be rewritten"


def test_unknown_version_rejected():
    with pytest.raises(ValueError):
        store.RunRecord.from_dict({"version": 3})


# ------------------------------------------------------------------ budgets and report
def _recs():
    return [
        store.RunRecord("r1", "hourly", T, "success", 30000, {"j": 30000}),
        store.RunRecord("r2", "hourly", T, "success", 20000, {"j": 20000}),
        store.RunRecord("r3", "nightly", T, "success", 50001, {"j": 50001}),
        store.RunRecord("r4", "adhoc", T, "success", 333, {"j": 333}),
    ]


def test_budgets_in_minor_units(tmp_path):
    path = tmp_path / "budgets.json"
    path.write_text('{"default_monthly_usd": 500, "pipelines": {"adhoc": "3.33"}}')
    config = budget.load_budgets(path)
    assert budget.budget_for(config, "hourly") == 50000
    assert budget.budget_for(config, "adhoc") == 333
    assert budget.month_to_date(_recs(), "hourly", "2026-09") == 50000
    alerts = budget.check(_recs(), config, "2026-09")
    assert [(a.pipeline, a.spent_minor, a.budget_minor) for a in alerts] == [("nightly", 50001, 50000)]


def test_sub_cent_budget_rejected(tmp_path):
    path = tmp_path / "budgets.json"
    path.write_text('{"default_monthly_usd": 500.005, "pipelines": {}}')
    with pytest.raises(ValueError):
        budget.budget_for(budget.load_budgets(path), "x")


def test_report_rows_add_up():
    text = report.monthly_report(_recs(), "2026-09")
    assert text == (
        "Spend for 2026-09\n"
        "\n"
        f"{'nightly':<24} {1:>4} runs  {'$500.01':>12}\n"
        f"{'hourly':<24} {2:>4} runs  {'$500.00':>12}\n"
        f"{'adhoc':<24} {1:>4} runs  {'$3.33':>12}\n"
        "\n"
        f"{'total':<24} {4:>4} runs  {'$1,003.34':>12}\n"
    )


# ------------------------------------------------------------------ CLI
def test_cli_price_and_record(tmp_path, capsys):
    specs, result = _three_jobs()
    run_path, specs_path, rates_path = tmp_path / "run.json", tmp_path / "specs.json", tmp_path / "rates.json"
    run_store.save(result, run_path)
    specs_path.write_text(json.dumps([s.to_dict() for s in specs.values()]))
    rates_path.write_text('{"warehouse": "0.0335"}')
    assert cli.main(["price", str(run_path), str(specs_path), "--rates", str(rates_path)]) == 0
    assert capsys.readouterr().out == f"{'a':<24} $0.34\n{'b':<24} $0.33\n{'c':<24} $0.33\n{'total':<24} $1.00\n"
    history = tmp_path / "h.jsonl"
    assert cli.main(["record", str(run_path), str(specs_path), "--rates", str(rates_path), "--pipeline", "p",
                     "--run-id", "r9", "--started-at", "2026-09-04T01:00:00+00:00", "--history", str(history)]) == 0
    doc = json.loads(history.read_text())
    assert doc["version"] == 2 and doc["total_minor"] == 100 and doc["jobs_minor"] == {"a": 34, "b": 33, "c": 33}

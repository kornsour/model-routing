"""Hidden grader: capacity planning without monotonicity (exp06 stratum B)."""

import json

import pytest

from orchestra import JobSpec
from orchestra.planning import anomalies, feasible, search, simulate

from ledger import cli
from ledger.planner import cheapest

DUR = {"T1": 3, "T2": 2, "T3": 2, "T4": 2, "T5": 4, "T6": 4, "T7": 4, "T8": 4, "T9": 9}
DEPS = {"T9": ("T1",), "T5": ("T4",), "T6": ("T4",), "T7": ("T4",), "T8": ("T4",)}


def graham():
    return [JobSpec(n, deps=DEPS.get(n, ()), duration=d, priority=9 - i, resources={"warehouse": 1}) for i, (n, d) in enumerate(DUR.items())]


def mixed():
    return graham() + [JobSpec("A1", duration=6, resources={"api": 1}), JobSpec("A2", duration=6, resources={"api": 1})]


def test_simulate_and_feasible():
    assert simulate(graham(), {"warehouse": 3}).makespan == 12
    assert simulate([JobSpec("big", resources={"warehouse": 2})], {"warehouse": 1}) is None
    assert feasible(graham(), {"warehouse": 3}, 12)
    assert not feasible(graham(), {"warehouse": 4}, 14)
    failing = [JobSpec("f", outcomes=("fail",))]
    assert not feasible(failing, {}, 100)


def test_anomalies():
    assert anomalies(graham(), "warehouse", {}, 1, 6) == [3]
    assert anomalies(mixed(), "warehouse", {"api": 2}, 2, 6) == [3]
    assert anomalies(mixed(), "api", {"warehouse": 3}, 1, 3) == []


def test_search_not_fooled_by_anomaly():
    plan = search(graham(), {"warehouse": (2, 6)}, 13)
    assert plan.capacities == {"warehouse": 3} and plan.makespan == 12 and plan.units == 3
    assert search(graham(), {"warehouse": (4, 4)}, 13) is None
    assert search(graham(), {"warehouse": (1, 6)}, 5) is None


def test_search_tie_breaks():
    # fewest units ties between (x=1, y=2) and (x=2, y=1): the lower makespan wins
    specs = [
        JobSpec("j0", duration=3, priority=2, resources={"y": 1}),
        JobSpec("j1", deps=("j0",), duration=1, priority=2, resources={"y": 1}),
        JobSpec("j2", duration=3, resources={"x": 1}),
        JobSpec("j3", duration=4, resources={"x": 1, "y": 1}),
        JobSpec("j4", deps=("j1",), duration=3, resources={"x": 1}),
    ]
    plan = search(specs, {"x": (1, 3), "y": (1, 3)}, 10)
    assert plan.capacities == {"x": 2, "y": 1} and plan.makespan == 8 and plan.units == 3
    # same units and makespan: the capacities tuple in sorted pool order decides
    specs = [
        JobSpec("j0", duration=1, resources={"x": 1, "y": 1}),
        JobSpec("j1", duration=2, resources={"x": 1}),
        JobSpec("j2", deps=("j1",), duration=3, resources={"y": 1}),
        JobSpec("j3", deps=("j1",), duration=1, resources={"y": 1}),
    ]
    plan = search(specs, {"x": (1, 3), "y": (1, 3)}, 6)
    assert plan.capacities == {"x": 1, "y": 2} and plan.makespan == 6


def test_bounds_validation():
    with pytest.raises(ValueError):
        search(graham(), {"warehouse": (0, 3)}, 20)
    with pytest.raises(ValueError):
        search(graham(), {"warehouse": (4, 3)}, 20)


RATES = {"warehouse": 1.0, "api": 10.0}


def test_cheapest_is_not_fewest_units():
    by_units = search(mixed(), {"warehouse": (2, 6), "api": (1, 3)}, 20)
    assert by_units.capacities == {"api": 1, "warehouse": 2} and by_units.makespan == 17
    plan = cheapest(mixed(), {"warehouse": (2, 6), "api": (1, 3)}, 20, RATES)
    assert plan.capacities == {"api": 1, "warehouse": 3}
    assert plan.makespan == 12 and plan.cost == pytest.approx(156.0)
    assert cheapest(mixed(), {"warehouse": (2, 6), "api": (1, 3)}, 5, RATES) is None


def test_cli_plan(tmp_path, capsys):
    specs = tmp_path / "specs.json"
    specs.write_text(json.dumps([s.to_dict() for s in mixed()]))
    rates = tmp_path / "rates.json"
    rates.write_text(json.dumps({"warehouse": "1.0", "api": "10.0"}))
    args = ["plan", str(specs), "--sla", "20", "--bounds", "warehouse=2:6,api=1:3", "--rates", str(rates)]
    assert cli.main(args) == 0
    assert capsys.readouterr().out.splitlines() == ["capacities: api=1 warehouse=3", "makespan: 12.0", "cost: $156.0000"]
    assert cli.main(args + ["--objective", "units"]) == 0
    assert capsys.readouterr().out.splitlines() == ["capacities: api=1 warehouse=2", "makespan: 17.0", "cost: $204.0000"]
    assert cli.main(["plan", str(specs), "--sla", "3", "--bounds", "warehouse=1:2,api=1:1", "--rates", str(rates)]) == 1
    assert capsys.readouterr().out.strip() == "no feasible plan"

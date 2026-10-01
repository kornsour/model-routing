import pytest

from orchestra import JobSpec

from ledger.planner import cheapest


def test_bigger_faster_pool_can_be_cheaper():
    specs = [JobSpec(f"j{i}", duration=10, resources={"w": 1}) for i in range(4)]
    plan = cheapest(specs, {"w": (1, 4)}, 100, {"w": 1.0})
    assert plan.cost == pytest.approx(40.0)

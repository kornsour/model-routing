from orchestra import JobSpec
from orchestra.planning import anomalies, search

DUR = [3, 2, 2, 2, 4, 4, 4, 4, 9]


def graham():
    deps = {9: (1,), 5: (4,), 6: (4,), 7: (4,), 8: (4,)}
    return [
        JobSpec(f"T{i}", deps=tuple(f"T{d}" for d in deps.get(i, ())), duration=DUR[i - 1], priority=9 - i, resources={"w": 1})
        for i in range(1, 10)
    ]


def test_graham_anomaly():
    assert anomalies(graham(), "w", {}, 1, 6) == [3]


def test_search_is_exhaustive():
    assert search(graham(), {"w": (2, 6)}, 13).capacities == {"w": 3}

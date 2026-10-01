import json

from orchestra import JobSpec, run
from orchestra.events import read_log, result_from_log


def test_log_round_trip(tmp_path):
    specs = [JobSpec("a", duration=1), JobSpec("b", deps=("a",), duration=2)]
    result = run(specs)
    for i, e in enumerate(result.events, start=1):
        (tmp_path / f"events-{i}.jsonl").write_text(json.dumps(e.to_dict()) + "\n")
    events = read_log(tmp_path.glob("events-*.jsonl"))
    assert events == result.events
    assert result_from_log(events, specs).runs == result.runs

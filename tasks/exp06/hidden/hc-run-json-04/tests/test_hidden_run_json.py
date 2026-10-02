"""Hidden grader: --json output (exp06 stratum C; keyed interpretation)."""

import json

from orchestra import JobSpec, run
from orchestra.cli import main
from orchestra.store import dumps, loads


def _pipeline(tmp_path):
    specs = [JobSpec("a_very_long_job_name_that_broke_the_table", duration=2, resources={"w": 1}),
             JobSpec("b", deps=("a_very_long_job_name_that_broke_the_table",), outcomes=("fail", "ok"), max_attempts=2, backoff=1)]
    path = tmp_path / "pipeline.json"
    path.write_text(json.dumps({"jobs": [s.to_dict() for s in specs], "capacities": {"w": 1}}))
    return specs, path


def test_json_is_the_run_file_format(tmp_path, capsys):
    specs, path = _pipeline(tmp_path)
    assert main(["run", str(path), "--json"]) == 0
    out = capsys.readouterr().out
    expected = run(specs, {"w": 1})
    assert out.strip() == dumps(expected)
    again = loads(out)
    assert again.runs == expected.runs and again.events == expected.events and again.makespan == expected.makespan


def test_table_unchanged(tmp_path, capsys):
    specs, path = _pipeline(tmp_path)
    assert main(["run", str(path)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].split() == ["job", "state", "attempts", "start", "finish"]
    assert lines[-1] == f"makespan: {run(specs, {'w': 1}).makespan:g}"

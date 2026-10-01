import json

from orchestra.cli import main
from orchestra.store import loads


def test_json_round_trips(tmp_path, capsys):
    path = tmp_path / "p.json"
    path.write_text(json.dumps({"jobs": [{"name": "a", "duration": 1}]}))
    assert main(["run", str(path), "--json"]) == 0
    assert loads(capsys.readouterr().out).makespan == 1

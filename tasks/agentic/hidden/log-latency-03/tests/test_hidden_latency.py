from logproc.cli import main

TOOK = ["850us", "3ms", "5ms", "12ms", "20ms", "40ms", "75ms", "120ms", "1.25s", "2.5s"]


def _log(tmp_path, tooks, extra=True):
    lines = []
    for i, took in enumerate(tooks):
        lines.append(f"2024-03-01T10:00:{i:02d} INFO GET /r{i} took={took} status=200")
        if extra:
            lines.append(f"2024-03-01T10:01:{i:02d} INFO heartbeat")
    if extra:
        lines.append("2024-03-01T10:02:00 WARNING GET /x took=fast")
    path = tmp_path / "app.log"
    path.write_text("\n".join(lines) + "\n")
    return path


def _latency(tmp_path, capsys, tooks, extra=True):
    assert main(["latency", str(_log(tmp_path, tooks, extra))]) == 0
    return capsys.readouterr().out.strip()


def _slow(tmp_path, capsys, over):
    assert main(["slow", str(_log(tmp_path, TOOK)), "--over", over]) == 0
    return [line.split(" ")[3] for line in capsys.readouterr().out.splitlines()]


# Brief: the latency numbers "must agree exactly with the README's Latency section", which
# counts every entry carrying a documented duration (fractional numbers included) and uses
# nearest-rank percentiles in milliseconds.
def test_latency_over_mixed_units_and_fractions(tmp_path, capsys):
    out = _latency(tmp_path, capsys, TOOK)
    assert out == "count=10 p50=20 p90=1250 p99=2500 max=2500"


# Brief: same sentence - nearest-rank percentiles, isolated from unit parsing.
def test_nearest_rank_percentiles(tmp_path, capsys):
    out = _latency(tmp_path, capsys, ["40ms", "10ms", "30ms", "20ms"], extra=False)
    assert out == "count=4 p50=20 p90=40 p99=40 max=40"


# Brief: same sentence - a two-sample p50 is the smaller sample under nearest-rank.
def test_nearest_rank_two_samples(tmp_path, capsys):
    out = _latency(tmp_path, capsys, ["1.5ms", "900ms"], extra=False)
    assert out == "count=2 p50=1.5 p90=900 p99=900 max=900"


# Brief: "`slow --over 0.5s` crashes"; README: the threshold is written the same way as a
# duration.
def test_slow_accepts_fractional_threshold(tmp_path, capsys):
    assert _slow(tmp_path, capsys, "0.5s") == ["/r8", "/r9"]


# README: `slow` lists entries that took "strictly longer than the threshold".
def test_slow_is_strict(tmp_path, capsys):
    assert _slow(tmp_path, capsys, "120ms") == ["/r8", "/r9"]
    assert _slow(tmp_path, capsys, "850us") == [f"/r{i}" for i in range(1, 10)]

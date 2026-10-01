"""Hidden grader: tamper-evident history (exp06 stratum B)."""

import hashlib
import json
from datetime import UTC, datetime

import pytest

from ledger import audit, cli, store

GENESIS = "0" * 64


def canonical(body):
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def chain_hash(prev, doc):
    body = {k: v for k, v in doc.items() if k not in ("prev_hash", "hash")}
    return hashlib.sha256((prev + canonical(body)).encode("utf-8")).hexdigest()


def rec(i, month, pipeline="nightly", total=1.5):
    return store.RunRecord(f"r{i}", pipeline, datetime(2026, month, 1 + i % 20, 2, tzinfo=UTC), "success", total, {"j": total})


def lines(path):
    return path.read_text().splitlines()


def build(tmp_path, n=6, legacy=0):
    path = tmp_path / "h.jsonl"
    for i in range(legacy):
        path.write_text(path.read_text() if path.exists() else "")
        with path.open("a") as f:
            f.write(json.dumps(rec(100 + i, 6).to_dict(), sort_keys=True) + "\n")
    for i in range(n):
        store.append(path, rec(i, 7 + i // 2, pipeline="nightly" if i % 2 else "hourly", total=1.25 * (i + 1)))
    return path


def test_append_chains_exactly(tmp_path):
    assert audit.GENESIS == GENESIS
    path = build(tmp_path, n=3)
    prev = GENESIS
    for line in lines(path):
        doc = json.loads(line)
        assert doc["prev_hash"] == prev
        assert doc["hash"] == chain_hash(prev, doc)
        prev = doc["hash"]
    assert [r.run_id for r in store.load(path)] == ["r0", "r1", "r2"]


def test_verify_ok_with_pre_chain(tmp_path):
    path = build(tmp_path, n=4, legacy=2)
    v = audit.verify(path)
    assert (v.ok, v.checked, v.pre_chain, v.checkpoints, v.bad_line, v.reason) == (True, 4, 2, 0, None, "")
    first_chained = json.loads(lines(path)[2])
    assert first_chained["prev_hash"] == GENESIS
    missing = audit.verify(tmp_path / "nope.jsonl")
    assert missing.ok and missing.checked == 0


def _rewrite(path, new_lines):
    path.write_text("".join(line + "\n" for line in new_lines))


def test_detects_edit(tmp_path):
    path = build(tmp_path)
    ls = lines(path)
    doc = json.loads(ls[2])
    doc["total_usd"] = 0.01
    ls[2] = json.dumps(doc, sort_keys=True)
    _rewrite(path, ls)
    v = audit.verify(path)
    assert not v.ok and v.bad_line == 3 and v.reason


def test_detects_delete_swap_and_late_unchained(tmp_path):
    path = build(tmp_path)
    original = lines(path)
    _rewrite(path, original[:2] + original[3:])
    assert audit.verify(path).bad_line == 3
    _rewrite(path, original[:1] + [original[2], original[1]] + original[3:])
    assert audit.verify(path).bad_line == 2
    late = json.dumps(rec(99, 9).to_dict(), sort_keys=True)
    _rewrite(path, original[:3] + [late] + original[3:])
    v = audit.verify(path)
    assert not v.ok and v.bad_line == 4


def test_compact_and_verify(tmp_path):
    path = build(tmp_path, n=6, legacy=1)  # chained months: r0,r1 -> 07, r2,r3 -> 08, r4,r5 -> 09
    original = lines(path)
    out = tmp_path / "compacted.jsonl"
    h = audit.compact(path, out, "2026-08")
    new = lines(out)
    assert new[0] == original[0]
    cp = json.loads(new[1])
    assert cp["kind"] == "checkpoint" and cp["covers"] == 2
    assert cp["through_hash"] == json.loads(original[2])["hash"]
    assert cp["prev_hash"] == GENESIS
    assert cp["summary"] == {"hourly": {"runs": 1, "total_usd": 1.25}, "nightly": {"runs": 1, "total_usd": 2.5}}
    assert cp["hash"] == chain_hash(cp["prev_hash"], cp) == h
    assert new[2:] == original[3:]
    v = audit.verify(out)
    assert (v.ok, v.checked, v.pre_chain, v.checkpoints) == (True, 4, 1, 1)
    assert [r.run_id for r in store.load(out)] == ["r100", "r2", "r3", "r4", "r5"]
    assert path.read_text().splitlines() == original
    with pytest.raises(FileExistsError):
        audit.compact(path, out, "2026-08")


def test_compact_twice_and_tampered_checkpoint(tmp_path):
    path = build(tmp_path, n=6)
    first, second = tmp_path / "c1.jsonl", tmp_path / "c2.jsonl"
    audit.compact(path, first, "2026-08")
    audit.compact(first, second, "2026-09")
    v = audit.verify(second)
    assert v.ok and v.checkpoints == 1 and v.checked == 2
    cp = json.loads(lines(second)[0])
    assert cp["covers"] == 4 and cp["prev_hash"] == GENESIS
    assert cp["summary"] == {"hourly": {"runs": 2, "total_usd": 5.0}, "nightly": {"runs": 2, "total_usd": 7.5}}
    ls = lines(second)
    doc = json.loads(ls[0])
    doc["summary"]["nightly"]["total_usd"] = 0.0
    ls[0] = json.dumps(doc, sort_keys=True)
    _rewrite(second, ls)
    assert audit.verify(second).bad_line == 1


def test_nothing_to_compact(tmp_path):
    path = build(tmp_path, n=2)
    out = tmp_path / "same.jsonl"
    assert audit.compact(path, out, "2026-01") == ""
    assert out.read_text() == path.read_text()


def test_cli(tmp_path, capsys):
    path = build(tmp_path, n=4, legacy=1)
    assert cli.main(["verify", "--history", str(path)]) == 0
    assert capsys.readouterr().out.strip() == "ok: 4 records verified (1 pre-chain, 0 checkpoints)"
    out = tmp_path / "c.jsonl"
    assert cli.main(["compact", "--before", "2026-08", "--out", str(out), "--history", str(path)]) == 0
    printed = capsys.readouterr().out.strip()
    assert printed == f"checkpoint {json.loads(lines(out)[1])['hash']}"
    ls = lines(path)
    _rewrite(path, ls[:2] + ls[3:])
    assert cli.main(["verify", "--history", str(path)]) == 1
    assert capsys.readouterr().out.startswith("FAILED at line 3: ")

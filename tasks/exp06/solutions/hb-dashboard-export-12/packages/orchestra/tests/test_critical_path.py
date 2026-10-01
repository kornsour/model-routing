from orchestra import DAG, JobSpec


def test_chain():
    specs = [JobSpec("a", duration=1), JobSpec("b", deps=("a",), duration=2), JobSpec("c", duration=2.5)]
    assert DAG(specs).critical_path() == (["a", "b"], 3.0)

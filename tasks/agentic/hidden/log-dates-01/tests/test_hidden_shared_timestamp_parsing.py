from logproc import pipeline


def test_pipeline_no_longer_defines_its_own_parse_timestamp():
    assert not hasattr(pipeline, "_parse_timestamp")

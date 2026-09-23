from logproc.aggregate import count_by_level


def test_count_by_level_empty_is_empty_dict():
    result = count_by_level([])
    assert result == {}

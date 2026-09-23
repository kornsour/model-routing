from logproc.retry import push_summary


def test_push_summary_success():
    sent = []

    def sender(summary):
        sent.append(summary)

    assert push_summary({"count": 2}, sender) is True
    assert sent == [{"count": 2}]

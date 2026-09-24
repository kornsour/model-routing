from logproc.retry import push_batches, push_summary


def test_push_summary_success():
    sent = []

    def sender(summary):
        sent.append(summary)

    assert push_summary({"count": 2}, sender) is True
    assert sent == [{"count": 2}]


def test_push_batches_happy_path():
    sent = []

    def sender(batch):
        sent.append(list(batch))

    summaries = [{"n": i} for i in range(5)]
    assert push_batches(summaries, sender, batch_size=2) == 5
    assert sent == [[{"n": 0}, {"n": 1}], [{"n": 2}, {"n": 3}], [{"n": 4}]]

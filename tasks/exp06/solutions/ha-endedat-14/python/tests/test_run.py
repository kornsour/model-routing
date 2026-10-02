import io
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runledger.run import Client  # noqa: E402


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class Recorder:
    def __init__(self, reply):
        self.reply = reply
        self.requests = []

    def __call__(self, req):
        self.requests.append(req)
        return FakeResponse(json.dumps(self.reply).encode())


class ClientTest(unittest.TestCase):
    def test_start_posts_the_run(self):
        rec = Recorder({"id": "r1", "status": "running", "started_at": "2026-09-01T10:00:00Z"})
        Client(opener=rec).start("r1", "train", config_hash="abc")
        payload = json.loads(rec.requests[0].data)
        self.assertEqual(payload["config_hash"], "abc")

    def test_finish_sends_ended_at(self):
        rec = Recorder({"id": "r1", "status": "succeeded", "ended_at": "2026-09-01T11:00:00Z"})
        Client(opener=rec).finish("r1")
        payload = json.loads(rec.requests[0].data)
        self.assertEqual(payload["status"], "succeeded")
        self.assertIn("ended_at", payload)

    def test_fresh_run_is_not_finished(self):
        # The server omits ended_at until a run ends.
        rec = Recorder({"id": "r1", "status": "running", "started_at": "2026-09-01T10:00:00Z"})
        run = Client(opener=rec).get("r1")
        self.assertNotIn("ended_at", run)
        self.assertFalse(Client(opener=rec).is_finished(run))


if __name__ == "__main__":
    unittest.main()

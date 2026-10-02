"""Python client for the trackbook HTTP API (stdlib only)."""

import json
import urllib.request
from datetime import datetime, timezone


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Client:
    def __init__(self, base_url: str = "http://127.0.0.1:8787", opener=urllib.request.urlopen):
        self.base_url = base_url.rstrip("/")
        self._open = opener

    def _send(self, method: str, path: str, payload: dict | None = None) -> dict:
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(self.base_url + path, data=data, method=method, headers={"Content-Type": "application/json"})
        with self._open(req) as resp:
            return json.loads(resp.read())

    def start(self, run_id: str, name: str, **provenance) -> dict:
        return self._send("POST", "/runs", {"id": run_id, "name": name, **provenance})

    def get(self, run_id: str) -> dict:
        return self._send("GET", f"/runs/{run_id}")

    def finish(self, run_id: str, status: str = "succeeded") -> dict:
        return self._send("PATCH", f"/runs/{run_id}", {"status": status, "ended_at": _utcnow()})

    def is_finished(self, run: dict) -> bool:
        return run.get("ended_at") is not None

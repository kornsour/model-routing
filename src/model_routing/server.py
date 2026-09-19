"""Loopback-only UI. Session token + strict origin/host checks protect paid actions."""

from __future__ import annotations

import json
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from model_routing.dashboard import build_payload, render_html
from model_routing.platform import Lab


def serve(root: Path, results: Path, port: int = 8765) -> None:
    lab: Lab
    token = secrets.token_urlsafe(32)
    server: ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        def reply(self, status: int, body: str, content: str = "application/json") -> None:
            self.send_response(status)
            self.send_header("Content-Type", content + "; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(body.encode())

        def allowed(self, write: bool = False) -> bool:
            host = f"127.0.0.1:{server.server_port}"
            if self.headers.get("Host") != host:
                return False
            if write:
                return (
                    self.headers.get("Origin") == "http://" + host
                    and self.headers.get("X-Lab-Token") == token
                    and self.headers.get("Content-Type") == "application/json"
                )
            return True

        def do_GET(self) -> None:
            if not self.allowed():
                self.reply(403, "{}")
                return
            path = urlsplit(self.path).path
            if path == "/":
                page = render_html(build_payload(lab.db, include_synthetic=True))
                controls = (
                    Path(__file__).with_name("lab.html").read_text().replace("__TOKEN__", token)
                )
                page = page.replace(
                    '<section id="lab" data-page-panel="overview"></section>',
                    '<section id="lab" data-page-panel="overview">' + controls + "</section>",
                )
                self.reply(200, page, "text/html")
            elif path == "/api/jobs":
                self.reply(200, json.dumps(lab.jobs()))
            elif path == "/api/results":
                self.reply(200, json.dumps(build_payload(lab.db, include_synthetic=True)))
            else:
                self.reply(404, "{}")

        def do_POST(self) -> None:
            if not self.allowed(True):
                self.reply(403, json.dumps({"error": "Local session required"}))
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 16000:
                    raise ValueError("Invalid request size")
                data: dict[str, Any] = json.loads(self.rfile.read(size))
                if self.path == "/api/estimate":
                    result = lab.estimate(data)
                elif self.path == "/api/start":
                    lab.start(str(data["id"]), float(data["budget"]), data.get("fake") is True)
                    result = {"state": "running"}
                else:
                    self.reply(404, "{}")
                    return
                self.reply(200, json.dumps(result))
            except (ValueError, KeyError, TypeError) as exc:
                self.reply(400, json.dumps({"error": str(exc)}))
            except Exception:
                self.reply(
                    500, json.dumps({"error": "Local operation failed; inspect server logs"})
                )
                raise

    from model_routing.store import index_results

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    lab = Lab(root, results)
    index_results(results, lab.db)
    print(f"Experiment lab: http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()

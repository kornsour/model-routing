"""Loopback-only UI. Session token + strict origin/host checks protect paid actions."""

from __future__ import annotations

import json
import secrets
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from model_routing import backup as backup_mod
from model_routing.backup import (
    Settings,
    backup_all,
    backup_run,
    backup_status,
    export_run,
    render_report_html,
    restore,
    set_auto_backup,
    set_backup_dir,
)
from model_routing.dashboard import build_payload, render_html
from model_routing.dispatch.web import DispatchLab
from model_routing.platform import Lab


def serve(
    root: Path,
    results: Path,
    port: int = 8765,
    *,
    open_browser: bool = False,
    page: str = "",
    token: str | None = None,
) -> None:
    lab: Lab
    dispatch_lab: DispatchLab
    token = token or secrets.token_urlsafe(32)
    server: ThreadingHTTPServer

    def safe_run_dir(dir_param: str) -> Path:
        if not dir_param:
            raise ValueError("Missing dir")
        base = results.resolve()
        candidate = (results / dir_param).resolve()
        if candidate != base and base not in candidate.parents:
            raise ValueError("Path must stay under results/")
        if not candidate.is_dir():
            raise ValueError("No such run directory")
        return candidate

    def safe_backup_dir(raw: str, create: bool = True) -> Path:
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            raise ValueError("Backup directory must be an absolute path")
        home = Path.home().resolve()
        try:
            resolved = candidate.resolve()
        except OSError as exc:
            raise ValueError("Invalid path") from exc
        if home != resolved and home not in resolved.parents:
            raise ValueError("Backup directory must be under your home directory")
        if not candidate.exists():
            if not create:
                raise ValueError("No such backup directory")
            try:
                candidate.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise ValueError(f"Could not create directory: {exc}") from exc
        return candidate

    class Handler(BaseHTTPRequestHandler):
        def reply(self, status: int, body: str, content: str = "application/json") -> None:
            self.send_response(status)
            self.send_header("Content-Type", content + "; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(body.encode())

        def reply_file(self, status: int, data: bytes, content: str, filename: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content)
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(data)

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
            elif path == "/dispatch":
                page = (
                    Path(__file__)
                    .with_name("dispatch")
                    .joinpath("web.html")
                    .read_text()
                    .replace("__TOKEN__", token)
                )
                self.reply(200, page, "text/html")
            elif path == "/api/jobs":
                self.reply(200, json.dumps(lab.jobs()))
            elif path == "/api/results":
                self.reply(200, json.dumps(build_payload(lab.db, include_synthetic=True)))
            elif path == "/api/dispatch/status":
                self.reply(200, json.dumps(dispatch_lab.status()))
            elif path == "/api/dispatch/run":
                qs = parse_qs(urlsplit(self.path).query)
                dir_param = (qs.get("dir") or [""])[0]
                try:
                    self.reply(200, json.dumps(dispatch_lab.get_run(dir_param)))
                except ValueError as exc:
                    self.reply(400, json.dumps({"error": str(exc)}))
            elif path == "/api/runs/export":
                qs = parse_qs(urlsplit(self.path).query)
                dir_param = (qs.get("dir") or [""])[0]
                try:
                    run_dir = safe_run_dir(dir_param)
                    with tempfile.TemporaryDirectory() as tmp:
                        zip_path = export_run(run_dir, out_dir=tmp)
                        self.reply_file(
                            200, zip_path.read_bytes(), "application/zip", zip_path.name
                        )
                except ValueError as exc:
                    self.reply(400, json.dumps({"error": str(exc)}))
            elif path == "/api/runs/report":
                qs = parse_qs(urlsplit(self.path).query)
                dir_param = (qs.get("dir") or [""])[0]
                try:
                    run_dir = safe_run_dir(dir_param)
                    self.reply(200, render_report_html(run_dir), "text/html")
                except ValueError as exc:
                    self.reply(400, json.dumps({"error": str(exc)}), "text/plain")
            elif path == "/api/backup/status":
                settings = Settings.load()
                self.reply(
                    200,
                    json.dumps(
                        {
                            "backup_dir": str(settings.backup_dir) if settings.backup_dir else None,
                            "auto_backup": settings.auto_backup,
                            "detected_drive": (
                                str(settings.detected_drive) if settings.detected_drive else None
                            ),
                            "runs": backup_status(results),
                            "index_snapshot": backup_mod.latest_index_snapshot(settings),
                        }
                    ),
                )
            else:
                self.reply(404, "{}")

        def do_POST(self) -> None:
            if not self.allowed(True):
                # Drain a small body first so the client sees the 403 rather than a reset.
                try:
                    pending = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    pending = 0
                if 0 < pending <= 16000:
                    self.rfile.read(pending)
                self.close_connection = True
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
                elif self.path == "/api/dispatch/estimate":
                    result = dispatch_lab.estimate(data)
                elif self.path == "/api/dispatch/start":
                    result = dispatch_lab.start(data)
                elif self.path == "/api/dispatch/cancel":
                    result = dispatch_lab.cancel()
                elif self.path == "/api/backup/run":
                    run_dir = safe_run_dir(str(data.get("dir", "")))
                    result = backup_run(run_dir)
                elif self.path == "/api/backup/all":
                    result = backup_all(results)
                elif self.path == "/api/backup/settings":
                    settings = Settings.load()
                    if "dir" in data and data["dir"]:
                        settings = set_backup_dir(safe_backup_dir(str(data["dir"])))
                    if "auto" in data:
                        settings = set_auto_backup(bool(data["auto"]))
                    result = {
                        "backup_dir": str(settings.backup_dir) if settings.backup_dir else None,
                        "auto_backup": settings.auto_backup,
                    }
                elif self.path == "/api/backup/restore":
                    backup_dir = safe_backup_dir(str(data.get("dir", "")), create=False)
                    result = restore(backup_dir, results)
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
    dispatch_lab = DispatchLab(root, results)
    index_results(results, lab.db)
    base_url = f"http://127.0.0.1:{server.server_port}"
    print(f"Experiment lab: {base_url}", flush=True)
    if open_browser:
        import webbrowser

        webbrowser.open(f"{base_url}/{page.lstrip('/')}" if page else base_url)
    try:
        server.serve_forever()
    finally:
        server.server_close()

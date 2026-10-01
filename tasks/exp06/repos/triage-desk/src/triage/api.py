"""HTTP surface (stdlib only). The caller's role arrives in X-Role."""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

from triage.actions import Action, ApprovalRequired, approve, execute_action
from triage.agent import triage_ticket
from triage.audit import AuditLog

AUDIT = AuditLog()
ACTIONS: dict[str, Action] = {}


def handle(method: str, path: str, role: str, body: dict) -> tuple[int, dict]:
    if method == "POST" and path == "/tickets/triage":
        return 200, triage_ticket(body, AUDIT, clearance=body.get("clearance", "public"))
    if method == "POST" and path == "/actions":
        action = Action(id=body["id"], kind=body["kind"], risk=int(body["risk"]))
        ACTIONS[action.id] = action
        return 201, {"id": action.id}
    if method == "POST" and path.startswith("/actions/") and path.endswith("/approve"):
        action = ACTIONS[path.split("/")[2]]
        try:
            approve(action, role, body.get("approver", "unknown"))
        except PermissionError as exc:
            return 403, {"error": str(exc)}
        return 200, {"approved": action.id}
    if method == "POST" and path.startswith("/actions/") and path.endswith("/execute"):
        action = ACTIONS[path.split("/")[2]]
        try:
            return 200, {"result": execute_action(action, AUDIT)}
        except ApprovalRequired:
            return 409, {"error": "approval required"}
    if method == "GET" and path == "/admin/audit":
        return 200, {"entries": AUDIT.entries, "valid": AUDIT.verify_chain()}
    return 404, {"error": "not found"}


class Handler(BaseHTTPRequestHandler):  # pragma: no cover - thin adapter
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("content-length", 0))) or b"{}")
        status, out = handle("POST", self.path, self.headers.get("X-Role", "agent"), body)
        self.send_response(status)
        self.end_headers()
        self.wfile.write(json.dumps(out).encode())

    def do_GET(self):
        status, out = handle("GET", self.path, self.headers.get("X-Role", "agent"), {})
        self.send_response(status)
        self.end_headers()
        self.wfile.write(json.dumps(out).encode())


if __name__ == "__main__":  # pragma: no cover
    HTTPServer(("127.0.0.1", 8088), Handler).serve_forever()

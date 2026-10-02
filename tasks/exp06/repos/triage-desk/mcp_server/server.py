"""MCP server over stdio (JSON-RPC 2.0, protocol 2025-06-18)."""

import json
import sys

from triage.rag import Retriever

TOOLS = {}


def tool(name, description, schema):
    def register(fn):
        TOOLS[name] = {"fn": fn, "description": description, "inputSchema": schema}
        return fn
    return register


@tool("search_kb", "Search the knowledge base", {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]})
def search_kb(query: str) -> list[dict]:
    return [{"doc": c.doc, "text": c.text} for c in Retriever().search(query)]


@tool("get_ticket", "Fetch a ticket by id", {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]})
def get_ticket(id: str) -> dict:
    return {"id": id, "subject": "VPN drops every hour", "status": "open"}


@tool("propose_action", "Propose a guarded action", {"type": "object", "properties": {"kind": {"type": "string"}, "risk": {"type": "integer"}}, "required": ["kind", "risk"]})
def propose_action(kind: str, risk: int) -> dict:
    return {"kind": kind, "risk": risk, "status": "pending_approval" if risk > 1 else "ready"}


def dispatch(request: dict) -> dict:
    method, rid = request.get("method"), request.get("id")
    if method == "initialize":
        result = {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}}, "serverInfo": {"name": "triage-desk", "version": "0.7.0"}}
    elif method == "tools/list":
        result = {"tools": [{"name": n, "description": t["description"], "inputSchema": t["inputSchema"]} for n, t in TOOLS.items()]}
    elif method == "tools/call":
        params = request["params"]
        out = TOOLS[params["name"]]["fn"](**params.get("arguments", {}))
        result = {"content": [{"type": "text", "text": json.dumps(out)}]}
    else:
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "method not found"}}
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def main() -> None:  # pragma: no cover - stdio loop
    for line in sys.stdin:
        if line.strip():
            print(json.dumps(dispatch(json.loads(line))), flush=True)


if __name__ == "__main__":  # pragma: no cover
    main()

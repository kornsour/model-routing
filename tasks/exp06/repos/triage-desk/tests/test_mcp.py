from mcp_server.server import dispatch


def test_tools_are_listed_and_callable():
    tools = dispatch({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})["result"]["tools"]
    assert {t["name"] for t in tools} == {"search_kb", "get_ticket", "propose_action"}
    out = dispatch({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "propose_action", "arguments": {"kind": "x", "risk": 2}}})
    assert "pending_approval" in out["result"]["content"][0]["text"]

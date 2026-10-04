"""Advisor request log and the frozen evidence rule (exp07).

Every advisor request a worker makes is recorded with what the worker had
seen when it asked. Two sources, both pass-through (nothing here can block or
change a request):

* **Hook** (``hook_main``): a Claude Code ``PreToolUse`` hook on the advisor
  tool, installed per session with ``--settings`` (``hook_settings``). It
  appends one JSON line per request to ``<sandbox>/.advisor_log/requests.jsonl``
  with the brief, the working-tree diff and the recent output, read from the
  session transcript. It is the only source of the diff (exp08's offline
  replay needs it). Whether Claude Code runs ``PreToolUse`` hooks for the
  server-side advisor tool is what exp07's first gate checks.
* **Stream** (``requests_from_stream``): the session's own
  ``--output-format stream-json`` events. Always available; gives the turn and
  the recent output, not the diff.

``evidence_label`` is the deterministic rule exp07 registers: a request is
``evidence_present`` when the last 4,000 characters of output before it show
a failing check (pytest, ``go test`` or ``node --test`` failure markers, or
the harness's own "not accepted" verifier message) or the same error line
twice. It labels what the worker had seen, not whether help was needed.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

LOG_DIR = ".advisor_log"
LOG_FILE = "requests.jsonl"
ADVISOR_TOOL = "advisor"
TAIL_CHARS = 4000
DIFF_CHARS = 24000

# --------------------------------------------------------------------------- #
# The frozen rule (registered with exp07; do not edit after registration)
# --------------------------------------------------------------------------- #

FAILURE_PATTERNS: tuple[str, ...] = (
    # pytest
    r"^FAILED\s",
    r"^ERROR\s",
    r"\b[1-9]\d* (?:failed|errors?)\b",
    r"^E\s{2,}\S",
    # go test
    r"^--- FAIL:",
    r"^FAIL\s+\S",
    # node --test (TAP)
    r"^not ok \d+",
    r"^# fail [1-9]",
    # the harness's verifier message to a resumed worker
    r"was checked and not accepted",
)
_FAILURE_RE = re.compile("|".join(f"(?:{p})" for p in FAILURE_PATTERNS), re.MULTILINE)
# "ValueError: ...", "error: ...", "Traceback ...": no word boundary before the
# keyword, so exception class names match.
_ERROR_LINE_RE = re.compile(r"(?:error|exception|traceback)\b", re.IGNORECASE)

RULE_VERSION = "exp07-v1"


def repeated_error_line(text: str) -> bool:
    seen: set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        if len(line) < 8 or not _ERROR_LINE_RE.search(line):
            continue
        if line in seen:
            return True
        seen.add(line)
    return False


def evidence_label(tail: str) -> str:
    """``evidence_present`` or ``no_evidence`` for the output a worker had seen."""
    tail = tail[-TAIL_CHARS:]
    if _FAILURE_RE.search(tail) or repeated_error_line(tail):
        return "evidence_present"
    return "no_evidence"


# --------------------------------------------------------------------------- #
# Reading transcripts / streams
# --------------------------------------------------------------------------- #


def _block_text(block: Any) -> str:
    if isinstance(block, str):
        return block
    if not isinstance(block, dict):
        return ""
    if block.get("type") == "text":
        return str(block.get("text") or "")
    if block.get("type") == "tool_result":
        content = block.get("content")
        if isinstance(content, list):
            return "\n".join(_block_text(b) for b in content)
        return str(content or "")
    return ""


def _is_advisor_call(block: Any) -> bool:
    return (
        isinstance(block, dict)
        and block.get("type") in ("tool_use", "server_tool_use")
        and block.get("name") == ADVISOR_TOOL
    )


def _messages(events: list[dict[str, Any]]) -> list[tuple[str, list[Any]]]:
    """(role, content blocks) for every user/assistant message, in order. Works
    for stream-json events and for transcript lines (both wrap a ``message``)."""
    out: list[tuple[str, list[Any]]] = []
    for ev in events:
        kind = ev.get("type")
        if kind not in ("user", "assistant"):
            continue
        content = (ev.get("message") or {}).get("content")
        if isinstance(content, str):
            content = [{"type": "text", "text": content}]
        out.append((kind, list(content or [])))
    return out


def _parse_lines(text: str) -> list[dict[str, Any]]:
    events = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def requests_from_stream(stdout: str) -> list[dict[str, Any]]:
    """Advisor requests found in a stream-json session, each with the output the
    worker had seen before it (tool results, later user messages, assistant
    text) and the evidence label."""
    requests: list[dict[str, Any]] = []
    seen: list[str] = []
    assistant_turn = 0
    first_user = True
    for role, blocks in _messages(_parse_lines(stdout)):
        if role == "assistant":
            assistant_turn += 1
        for block in blocks:
            if role == "assistant" and _is_advisor_call(block):
                tail = "\n".join(seen)[-TAIL_CHARS:]
                requests.append(
                    {
                        "source": "stream",
                        "assistant_turn": assistant_turn,
                        "question": json.dumps(block.get("input") or {})[:2000],
                        "tail": tail,
                        "label": evidence_label(tail),
                        "rule": RULE_VERSION,
                    }
                )
                continue
            if (
                role == "user"
                and first_user
                and not (isinstance(block, dict) and block.get("type") == "tool_result")
            ):
                continue  # the brief itself is not output
            text = _block_text(block)
            if text:
                seen.append(text)
        if role == "user":
            first_user = False
    return requests


# --------------------------------------------------------------------------- #
# The hook
# --------------------------------------------------------------------------- #


def hook_settings(python: str | None = None) -> dict[str, Any]:
    """``--settings`` JSON installing the pass-through PreToolUse hook."""
    exe = python or sys.executable
    return {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": ADVISOR_TOOL,
                    "hooks": [
                        {
                            "type": "command",
                            "command": f'"{exe}" -m model_routing.dispatch.advisor_log hook',
                            "timeout": 30,
                        }
                    ],
                }
            ]
        }
    }


def _git_diff(cwd: Path) -> str:
    try:
        tracked = subprocess.run(
            ["git", "diff", "HEAD"], cwd=cwd, capture_output=True, text=True, timeout=20
        ).stdout
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=20,
        ).stdout.split()
    except (OSError, subprocess.SubprocessError):
        return ""
    parts = [tracked]
    for rel in untracked:
        if rel.startswith((LOG_DIR + "/", ".verifier/")):
            continue
        try:
            body = (cwd / rel).read_text(errors="replace")
        except OSError:
            continue
        parts.append(
            f"--- /dev/null\n+++ b/{rel}\n" + "".join(f"+{ln}\n" for ln in body.splitlines())
        )
    return "".join(parts)[:DIFF_CHARS]


def snapshot_from_transcript(transcript_text: str) -> dict[str, str]:
    """The brief, recent worker output and recent tool output in a transcript."""
    brief = ""
    worker: list[str] = []
    tools: list[str] = []
    seen: list[str] = []
    for role, blocks in _messages(_parse_lines(transcript_text)):
        for block in blocks:
            text = _block_text(block)
            if not text:
                continue
            is_result = isinstance(block, dict) and block.get("type") == "tool_result"
            if role == "user" and not brief and not is_result:
                brief = text
                continue
            seen.append(text)
            (tools if is_result else worker).append(text)
    return {
        "brief": brief,
        "worker_tail": "\n".join(worker)[-TAIL_CHARS:],
        "tool_tail": "\n".join(tools)[-TAIL_CHARS:],
        "tail": "\n".join(seen)[-TAIL_CHARS:],
    }


def record_hook_request(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Write one request line for a PreToolUse payload; never raises."""
    try:
        cwd = Path(payload.get("cwd") or ".")
        transcript = ""
        tpath = payload.get("transcript_path")
        if tpath and Path(tpath).is_file():
            transcript = Path(tpath).read_text(errors="replace")
        snap = snapshot_from_transcript(transcript)
        entry = {
            "source": "hook",
            "session_id": payload.get("session_id"),
            "tool_name": payload.get("tool_name"),
            "question": json.dumps(payload.get("tool_input") or {})[:2000],
            "brief": snap["brief"],
            "diff": _git_diff(cwd),
            "worker_tail": snap["worker_tail"],
            "tool_tail": snap["tool_tail"],
            "tail": snap["tail"],
            "label": evidence_label(snap["tail"]),
            "rule": RULE_VERSION,
        }
        log = cwd / LOG_DIR
        log.mkdir(exist_ok=True)
        with (log / LOG_FILE).open("a") as fh:
            fh.write(json.dumps(entry) + "\n")
        return entry
    except Exception:  # a logging failure must never affect the session
        return None


def hook_main(stdin_text: str) -> int:
    try:
        payload = json.loads(stdin_text or "{}")
    except json.JSONDecodeError:
        return 0
    if isinstance(payload, dict):
        record_hook_request(payload)
    return 0  # exit 0, no output: the request proceeds unchanged


def read_and_clear(sandbox: str | Path) -> list[dict[str, Any]]:
    """Requests the hook logged in this sandbox since the last call."""
    path = Path(sandbox) / LOG_DIR / LOG_FILE
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    path.unlink()
    return rows


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "hook":
        sys.exit(hook_main(sys.stdin.read()))
    print("usage: python -m model_routing.dispatch.advisor_log hook < payload.json")
    sys.exit(2)

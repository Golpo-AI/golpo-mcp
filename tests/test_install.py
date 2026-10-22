"""Install checks: the server must start the way the README tells people to run it.

`test_server_answers_over_stdio` starts the server as a subprocess and does the
MCP handshake (initialize, then tools/list). By default it runs
`python -m golpo_mcp` from the current environment. CI also runs it against the
README install line, `uvx golpo-mcp`, on the freshly built wheel, by setting
GOLPO_MCP_SMOKE_CMD. No Golpo API key and no network access to Golpo are needed.
"""

from __future__ import annotations

import json
import os
import queue
import shlex
import subprocess
import sys
import threading
import time
from importlib.metadata import requires

import pytest

EXPECTED_TOOLS = {
    "generate_video", "upload_file", "list_videos",
    "get_video", "check_status", "status",
}
TIMEOUT_S = float(os.environ.get("GOLPO_MCP_SMOKE_TIMEOUT", "120"))


def test_mcp_requirement_excludes_2x():
    """mcp 2.0 removed mcp.server.fastmcp; the declared range must stop below it."""
    from packaging.requirements import Requirement

    reqs = [Requirement(r) for r in requires("golpo-mcp") or []]
    (mcp_req,) = [r for r in reqs if r.name == "mcp"]
    assert "2.0.0" not in mcp_req.specifier, f"mcp requirement allows 2.x: {mcp_req}"


def _server_command() -> list[str]:
    override = os.environ.get("GOLPO_MCP_SMOKE_CMD")
    if override:
        return shlex.split(override)
    return [sys.executable, "-m", "golpo_mcp"]


def test_server_answers_over_stdio(tmp_path):
    env = {k: v for k, v in os.environ.items() if k != "GOLPO_API_KEY"}
    env["HOME"] = str(tmp_path)  # no ~/.golpo key file either
    proc = subprocess.Popen(
        _server_command(),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    lines: queue.Queue = queue.Queue()
    threading.Thread(target=lambda: [lines.put(x) for x in proc.stdout], daemon=True).start()
    stderr: list[str] = []
    threading.Thread(target=lambda: stderr.extend(proc.stderr), daemon=True).start()

    def send(msg: dict) -> None:
        proc.stdin.write(json.dumps(msg) + "\n")
        proc.stdin.flush()

    def reply(msg_id: int) -> dict:
        deadline = time.monotonic() + TIMEOUT_S
        while time.monotonic() < deadline:
            try:
                line = lines.get(timeout=0.2)
            except queue.Empty:
                if proc.poll() is not None:
                    break
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("id") == msg_id:
                return msg
        time.sleep(0.2)
        pytest.fail(
            f"no reply to request {msg_id}; server exit code {proc.poll()}; "
            "stderr tail:\n" + "".join(stderr[-15:])
        )

    try:
        send({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "golpo-mcp-tests", "version": "0"},
            },
        })
        init = reply(1)
        assert init["result"]["serverInfo"]["name"] == "golpo"
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        names = {tool["name"] for tool in reply(2)["result"]["tools"]}
        assert EXPECTED_TOOLS <= names, f"missing tools: {EXPECTED_TOOLS - names}"
    finally:
        proc.stdin.close()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

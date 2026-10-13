#!/usr/bin/env python3
"""Check both configured Kata MCP adapters; --pilot appends retry-safe task evidence."""

import argparse
import json
import os
import selectors
import subprocess
import sys
import time

from local_env import ROOT, base_environment


class StdioClient:
    def __init__(self, actor):
        self.process = subprocess.Popen(
            [sys.executable, str(ROOT / "scripts/kata-mcp.py"), actor],
            cwd=ROOT, env=base_environment(), stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.process.stdout, selectors.EVENT_READ)
        self.buffer = b""
        self.sequence = 0
        self.tool_changes = 0

    def send(self, method, params, request_id=None):
        message = {"jsonrpc": "2.0", "method": method, "params": params}
        if request_id is not None:
            message["id"] = request_id
        self.process.stdin.write(json.dumps(message).encode() + b"\n")
        self.process.stdin.flush()

    def request(self, method, params):
        self.sequence += 1
        request_id = self.sequence
        self.send(method, params, request_id)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            while b"\n" in self.buffer:
                line, self.buffer = self.buffer.split(b"\n", 1)
                message = json.loads(line)
                if message.get("method") == "notifications/tools/list_changed":
                    self.tool_changes += 1
                if message.get("id") == request_id:
                    if "error" in message:
                        raise RuntimeError(f"MCP {method} failed: {message['error']['message']}")
                    return message["result"]
            if self.selector.select(max(0, deadline - time.monotonic())):
                chunk = os.read(self.process.stdout.fileno(), 65536)
                if not chunk:
                    raise RuntimeError("Kata MCP exited before responding")
                self.buffer += chunk
        raise RuntimeError(f"Kata MCP timed out: {method}")

    def tool(self, name, arguments):
        return self.request("tools/call", {"name": name, "arguments": arguments})

    def close(self):
        self.process.stdin.close()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            self.process.wait(timeout=5)
            raise RuntimeError("Kata MCP required termination after its input closed") from None
        finally:
            self.selector.close()
            self.process.stdout.close()
            self.process.stderr.close()
        if self.process.returncode:
            raise RuntimeError(f"Kata MCP exited with status {self.process.returncode}")


def data(result):
    if result.get("isError"):
        raise RuntimeError("Kata MCP returned a tool error")
    return result["structuredContent"]


def scope_refused(result):
    text = " ".join(block.get("text", "") for block in result.get("content", []))
    return result.get("isError") is True and "scope" in text.lower()


def check(actor, pilot):
    client = StdioClient(actor)
    try:
        client.request("initialize", {
            "protocolVersion": "2025-03-26", "capabilities": {},
            "clientInfo": {"name": "engi-platform-kata-check", "version": "1"},
        })
        client.send("notifications/initialized", {})
        initial = client.request("tools/list", {})
        for section in ("issue_discovery", "coordination", "issue_mutation"):
            data(client.tool("kata.load_" + section, {}))
        names = {tool["name"] for tool in client.request("tools/list", {})["tools"]}
        if not {"kata.show", "kata.claim", "kata.comment", "kata.status", "kata.inbox"} <= names:
            raise RuntimeError("Kata progressive tools were not rediscovered")
        shown = data(client.tool("kata.show", {"ref": "tvbf"}))
        status = data(client.tool("kata.status", {"ref": "tvbf"}))
        if shown["project"]["name"] != "engi-platform" or status["actor"] != actor:
            raise RuntimeError("Kata MCP scope or fixed actor is incorrect")
        outside = client.tool("kata.show", {"ref": "kata-evaluation-20261012#abcd"})
        outside_write = client.tool("kata.comment", {
            "ref": "kata-evaluation-20261012#abcd",
            "body": "This cross-project request must be refused before any mutation.",
            "idempotency_key": f"engi-kata-scope-refusal-{actor}",
        })
        if not scope_refused(outside) or not scope_refused(outside_write):
            raise RuntimeError("Kata MCP did not explicitly refuse cross-project read/write scope")
        inbox = data(client.tool("kata.inbox", {"for": actor, "limit": 10}))
        if inbox["recipient"] != actor:
            raise RuntimeError("Kata inbox recipient was not preserved")
        if pilot:
            if actor == "pi":
                if status.get("owner") != "copilot":
                    raise RuntimeError("Pilot expects tvbf to remain claimed by copilot")
                conflict = client.tool("kata.claim", {"ref": "tvbf", "if_unowned": True})
                if conflict.get("isError") is not True:
                    raise RuntimeError("Pi unexpectedly replaced Copilot's existing claim")
            result = data(client.tool("kata.comment", {
                "ref": "tvbf",
                "body": f"{actor} adapter pilot: native scoped MCP initialized; lazy catalog refreshed; "
                        "tvbf read and inbox access succeeded; cross-project access was refused. "
                        "This is transport/tool execution evidence, not model-selected behavior or "
                        "native attention-hook verification. Model calls: zero.",
                "idempotency_key": f"engi-kata-adapter-pilot-20261012-{actor}",
            }))
            repeated = data(client.tool("kata.comment", {
                "ref": "tvbf", "body": result["comment"]["body"],
                "idempotency_key": f"engi-kata-adapter-pilot-20261012-{actor}",
            }))
            if result["comment"]["author"] != actor or repeated["changed"]:
                raise RuntimeError("Kata mutation actor or comment retry safety is incorrect")
        return {
            "actor": actor, "project": shown["project"]["name"],
            "initial_tools": len(initial["tools"]), "loaded_tools": len(names),
            "tool_change_notifications": client.tool_changes,
            "cross_project_read_write_refused": True, "pilot_comment": pilot, "model_calls": 0,
        }
    finally:
        client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", action="store_true",
                        help="append idempotent Pi/Copilot comments to real integration task tvbf")
    args = parser.parse_args()
    results = [check(actor, args.pilot) for actor in ("pi", "copilot")]
    print(json.dumps({"ok": True, "adapters": results}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)

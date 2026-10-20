#!/usr/bin/env python3
"""Exercise real SDK clients; these results never certify outer-session access."""
from __future__ import annotations

import argparse
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import socket
import sys
from urllib.parse import urlsplit
import uuid

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.client.stdio import StdioServerParameters
from mcp.types import Implementation

from probe import DIAGNOSTIC_MARKER, PACKET_ID, PACKET_VERSION, ROOT, digest, packet

EXPECTED_TOOLS = {"xorder_probe_status", "xorder_catalog_search", "xorder_context_get", "xorder_probe_check"}


def require(condition, message):
    if not condition:
        raise AssertionError(message)


async def exercise(target, transport, mode):
    challenge = uuid.uuid4().hex
    async with asyncio.timeout(25):
        async with Client(target, mode=mode, read_timeout_seconds=5,
                          client_info=Implementation(name="xorder-fixture-smoke", version="0.1.0")) as client:
            tools = await client.list_tools()
            require({tool.name for tool in tools.tools} == EXPECTED_TOOLS, "Unexpected tool discovery")
            response = await client.call_tool("xorder_probe_status", {"challenge": challenge})
            require(not response.is_error, "Status failed")
            observed = response.structured_content
            require(observed["challenge"] == challenge, "Fresh challenge was not echoed")
            search = await client.call_tool("xorder_catalog_search", {"query": "test kit"})
            require(search.structured_content["items"][0]["id"] == PACKET_ID, "Fixture discovery failed")
            full = await client.call_tool("xorder_context_get", {"packet_id": PACKET_ID, "version": PACKET_VERSION})
            require(not full.is_error, "Packet retrieval failed")
            value = full.structured_content
            require(value == packet(), "Packet differs from this fixture's known bytes")
            require(digest(value["content"].encode()) == value["packet_sha256"], "Full payload digest mismatch")
            usage = await client.call_tool("xorder_context_get", {"section": "usage"})
            require(usage.structured_content == packet(section="usage"), "Section digest/content mismatch")
            unknown = await client.call_tool("xorder_context_get", {"version": "absent"})
            require(unknown.is_error, "Unknown identity was accepted")
            oversized = await client.call_tool("xorder_catalog_search", {"query": "x" * 257})
            require(oversized.is_error, "Oversized input was accepted")
            negative = await client.call_tool("xorder_probe_check", {})
            require(negative.is_error and DIAGNOSTIC_MARKER in negative.model_dump_json(), "Diagnostic missing")
            retry = await client.call_tool("xorder_probe_check", {"receipt": "packet-ack-v1"})
            require(not retry.is_error and retry.structured_content["passed"], "Receipt retry failed")
            return {"transport": transport, "status": "passed", "challenge": challenge,
                    "server": observed, "protocol_version": client.protocol_version,
                    "tools": sorted(EXPECTED_TOOLS), "packet_sha256": value["packet_sha256"],
                    "checks": ["discovery", "fresh-challenge", "exact-packet", "section-digest",
                               "unknown-identity-error", "input-bound", "diagnostic-error", "receipt-retry"],
                    "caller": "SDK test client; not a cloud conversation"}


@asynccontextmanager
async def local_http():
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    process = await asyncio.create_subprocess_exec(
        sys.executable, str(ROOT / "probe.py"), "serve", "--transport", "http", "--port", str(port),
        stdout=sys.stderr, stderr=sys.stderr)
    try:
        async with asyncio.timeout(10):
            while True:
                if process.returncode is not None:
                    raise RuntimeError("HTTP fixture exited before readiness")
                try:
                    _, writer = await asyncio.open_connection("127.0.0.1", port)
                    writer.close()
                    await writer.wait_closed()
                    break
                except OSError:
                    await asyncio.sleep(0.05)
        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        if process.returncode is None:
            process.terminate()
        try:
            await asyncio.wait_for(process.wait(), 3)
        except TimeoutError:
            process.kill()
            await process.wait()


async def exercise_http(url, transport, mode):
    parsed = urlsplit(url)
    require(parsed.scheme in ("http", "https") and parsed.hostname, "Expected an HTTP(S) endpoint")
    require(not (parsed.username or parsed.password or parsed.query or parsed.fragment), "Use a fixture URL without credentials, query or fragment")
    loopback = parsed.hostname in ("127.0.0.1", "localhost", "::1")
    async with httpx2.AsyncClient(trust_env=not loopback, timeout=5, follow_redirects=True) as http:
        return await exercise(streamable_http_client(url, http_client=http), transport, mode)


async def run(args, results):
    if args.url:
        results.append(await exercise_http(args.url, "http-explicit-endpoint", args.protocol_mode))
    elif args.stdio_command:
        command = args.stdio_command
        results.append(await exercise(StdioServerParameters(command=command[0], args=command[1:]), "stdio-explicit-command", args.protocol_mode))
    else:
        target = StdioServerParameters(command=sys.executable, args=[str(ROOT / "probe.py"), "serve"])
        results.append(await exercise(target, "stdio", args.protocol_mode))
        async with local_http() as url:
            results.append(await exercise_http(url, "http-loopback", args.protocol_mode))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--protocol-mode", choices=("auto", "legacy"), default="auto",
                        help="SDK auto negotiation or legacy initialization handshake")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--url", help="Explicit fixture MCP URL; do not include credentials")
    group.add_argument("--stdio-command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    report = {"schema_version": 1, "observed_at": datetime.now(timezone.utc).isoformat(),
              "evidence_kind": "sdk-client", "protocol_mode": args.protocol_mode,
              "outer_session_registration": "not_tested",
              "native_hook_delivery": "not_tested", "fresh_session_persistence": "not_tested",
              "fixture_files_sha256": {name: digest((ROOT / name).read_bytes()) for name in
                                       ("probe.py", "smoke.py", "packet.md", "manifest.json", "requirements.lock")},
              "observations": []}
    try:
        asyncio.run(run(args, report["observations"]))
        report["status"] = "passed"
    except Exception as error:
        report.update(status="failed", error_type=type(error).__name__)
        # The traceback is useful locally; reports contain only synthetic observations.
        import traceback
        traceback.print_exc(file=sys.stderr)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text, end="")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

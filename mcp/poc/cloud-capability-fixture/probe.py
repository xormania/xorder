#!/usr/bin/env python3
"""Small, synthetic cloud fixture. This is not the production xorder server."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import sys
from typing import Any
import uuid

ROOT = Path(__file__).resolve().parent
PACKET_ID = "context/poc-test-kit"
PACKET_VERSION = "0.0.0-poc.1"
FIXTURE_VERSION = "0.1.0"
DIAGNOSTIC_MARKER = "xorder-poc-diagnostic-v1"
BOOT_ID = str(uuid.uuid4())
TOKEN = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
HOOK_EVENTS = ("SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "PostToolUseFailure")


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def token(value: str) -> str:
    if not TOKEN.fullmatch(value):
        raise ValueError("Use a non-secret token of 1-64 letters, digits, underscores or hyphens")
    return value


def packet(packet_id=PACKET_ID, version=PACKET_VERSION, section=None):
    if packet_id != PACKET_ID or version != PACKET_VERSION:
        raise ValueError("Unknown experimental packet identity")
    raw = (ROOT / "packet.md").read_bytes()
    manifest = json.loads((ROOT / "manifest.json").read_text())
    if digest(raw) != manifest["packet_sha256"]:
        raise ValueError("Fixture packet integrity mismatch")
    content = raw.decode("utf-8")
    if section is not None:
        if section not in ("overview", "usage"):
            raise ValueError("Unknown section; choose overview or usage")
        content = content.split("## " + section + "\n", 1)[1].split("\n## ", 1)[0]
    return {"id": PACKET_ID, "version": PACKET_VERSION, "experimental": True,
            "packet_sha256": manifest["packet_sha256"], "section": section,
            "content_sha256": digest(content.encode()), "content": content,
            "source": "bundled-fixture/packet.md"}


def status(challenge: str) -> dict:
    return {"fixture_version": FIXTURE_VERSION, "boot_id": BOOT_ID,
            "challenge": token(challenge), "packet_sha256": packet()["packet_sha256"],
            "sdk": "mcp", "sdk_version": importlib.metadata.version("mcp"),
            "python": platform.python_version(), "platform": platform.system(),
            "architecture": platform.machine(), "uid": os.getuid() if hasattr(os, "getuid") else None,
            "source_commit": os.environ.get("XORDER_PROBE_SOURCE", "unrecorded"),
            "scope": "fixture-process; caller identity must be recorded separately"}


def diagnostic(challenge: str) -> str:
    return (f"{DIAGNOSTIC_MARKER} challenge={token(challenge)}. "
            f"Retrieve {PACKET_ID} at {PACKET_VERSION} using xorder_context_get; "
            "its usage section explains the fixture receipt. This is advisory probe feedback.")


def hook(challenge: str, raw: str) -> dict:
    event = json.loads(raw)
    if not isinstance(event, dict) or event.get("hook_event_name") not in HOOK_EVENTS:
        raise ValueError("Unsupported hook_event_name")
    # Keep arbitrary prompts, tool arguments, paths and transcripts out of output.
    return {"hookSpecificOutput": {"hookEventName": event["hook_event_name"],
                                   "additionalContext": diagnostic(challenge)}}


def state(action: str, directory: Path, challenge: str) -> dict:
    """Explicit local marker, never exposed as an MCP filesystem operation."""
    path = directory / (token(challenge) + ".json")
    if action == "create":
        directory.mkdir(parents=True, exist_ok=True)
        payload = {"schema_version": 1, "challenge": challenge,
                   "marker": str(uuid.uuid4()), "fixture_version": FIXTURE_VERSION}
        # Exclusive create: observing existing state must not recreate or replace it.
        with path.open("x", encoding="utf-8") as stream:
            json.dump(payload, stream, sort_keys=True)
            stream.write("\n")
    if path.is_symlink():
        raise ValueError("State marker must be a regular file")
    with path.open("rb") as stream:
        data = stream.read(4097)
    if len(data) > 4096:
        raise ValueError("State marker is too large")
    payload = json.loads(data)
    if payload.get("challenge") != challenge or payload.get("schema_version") != 1:
        raise ValueError("State marker identity mismatch")
    return {"state": payload, "sha256": digest(data), "observation": "file-read",
            "scope": "this path only; session persistence requires a later independent read"}


def serve(args):
    from typing import Annotated, Literal
    from mcp.server import MCPServer
    from mcp.server.mcpserver.exceptions import ToolError
    from mcp.server.transport_security import TransportSecuritySettings
    from mcp.types import ToolAnnotations
    from pydantic import Field

    annotations = ToolAnnotations(read_only_hint=True, destructive_hint=False,
                                  idempotent_hint=True, open_world_hint=False)
    server = MCPServer("xorder-cloud-capability-fixture", version=FIXTURE_VERSION,
                       instructions="Synthetic capability fixture; no accepted catalog releases.",
                       log_level="WARNING")

    def trace(operation, challenge=None):
        print(json.dumps({"event": "fixture-call", "operation": operation,
                          "boot_id": BOOT_ID, "challenge": challenge}), file=sys.stderr, flush=True)

    def xorder_probe_status(challenge: Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")]) -> dict[str, Any]:
        """Echo a fresh non-secret challenge and identify the responding fixture process."""
        result = status(challenge)
        trace("xorder_probe_status", challenge)
        return result

    def xorder_catalog_search(query: Annotated[str, Field(max_length=256)] = "") -> dict[str, Any]:
        """Search this one experimental test-kit packet; not the production catalog."""
        terms = "context poc test kit testing fixture engineering".split()
        match = not query.strip() or any(word in query.lower() for word in terms)
        trace("xorder_catalog_search")
        return {"experimental": True, "items": [{"id": PACKET_ID, "version": PACKET_VERSION,
                 "packet_sha256": packet()["packet_sha256"], "sections": ["overview", "usage"]}] if match else []}

    def xorder_context_get(packet_id: Annotated[str, Field(max_length=128)] = PACKET_ID,
                           version: Annotated[str, Field(max_length=64)] = PACKET_VERSION,
                           section: Literal["overview", "usage"] | None = None) -> dict[str, Any]:
        """Return exact fixture bytes, packet digest, and selected-content digest."""
        trace("xorder_context_get")
        try:
            return packet(packet_id, version, section)
        except ValueError as error:
            raise ToolError(str(error)) from None

    def xorder_probe_check(receipt: Annotated[str, Field(max_length=64)] = "") -> dict[str, Any]:
        """Exercise diagnostic feedback; the context packet explains the expected receipt."""
        trace("xorder_probe_check")
        if receipt != "packet-ack-v1":
            raise ToolError(diagnostic("tool-feedback"))
        return {"passed": True, "marker": "xorder-poc-context-v1",
                "meaning": "fixture receipt accepted; useful task behavior is not established"}

    for function in (xorder_probe_status, xorder_catalog_search, xorder_context_get, xorder_probe_check):
        server.tool(annotations=annotations, structured_output=True)(function)
    if args.transport == "stdio":
        server.run()
    else:
        security = TransportSecuritySettings(
            allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*", *args.allow_host],
            allowed_origins=["http://127.0.0.1:*", "http://localhost:*", *args.allow_origin])
        server.run(transport="streamable-http", host=args.host, port=args.port,
                   json_response=True, stateless_http=True, max_request_body_size=16384,
                   transport_security=security)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    http = sub.add_parser("serve")
    http.add_argument("--transport", choices=("stdio", "http"), default="stdio")
    http.add_argument("--host", default="127.0.0.1")
    http.add_argument("--port", type=int, default=8000)
    http.add_argument("--allow-host", action="append", default=[])
    http.add_argument("--allow-origin", action="append", default=[])
    info = sub.add_parser("info")
    info.add_argument("--challenge", default="manual-info")
    diag = sub.add_parser("diagnostic")
    diag.add_argument("--challenge", required=True)
    diag.add_argument("--format", choices=("json", "claude-hook"), default="json")
    persist = sub.add_parser("state")
    persist.add_argument("action", choices=("create", "read"))
    persist.add_argument("--directory", type=Path, required=True)
    persist.add_argument("--challenge", required=True)
    args = parser.parse_args()
    try:
        if args.command == "serve":
            serve(args)
            return
        if args.command == "info":
            result = status(args.challenge)
        elif args.command == "state":
            result = state(args.action, args.directory, args.challenge)
        elif args.format == "claude-hook":
            raw = sys.stdin.read(65537)
            if len(raw) > 65536:
                raise ValueError("Hook input exceeds fixture limit of 65536 characters")
            result = hook(args.challenge, raw)
        else:
            result = {"marker": DIAGNOSTIC_MARKER, "message": diagnostic(args.challenge), "advisory": True}
        print(json.dumps(result, sort_keys=True))
    except (ValueError, OSError) as error:
        # Do not echo malformed native event input or private filesystem paths.
        print(json.dumps({"error": type(error).__name__, "message": "Fixture command failed; check input and path permissions"}), file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()

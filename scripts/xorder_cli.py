#!/usr/bin/env python3
"""Optional xorder discovery helper; Python 3 and requirements-ci.txt are required."""
import argparse
import hashlib
from pathlib import Path
from jsonschema.exceptions import ValidationError

from xorder import model
from xorder.resolve import resolve


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=model.ROOT, help="repository root")
    sub = parser.add_subparsers(dest="command", required=True)
    listing = sub.add_parser("list")
    listing.add_argument("--kind", choices=("image",) + model.KINDS)
    listing.add_argument("--all", action="store_true", help="include withdrawn/deprecated releases")
    listing.add_argument("--latest", action="store_true", help="one latest eligible release per resource")
    listing.add_argument("--summary", action="store_true", help="concise identities, prerequisites and usage links")
    showing = sub.add_parser("show")
    showing.add_argument("id")
    showing.add_argument("--version", help="one explicit release revision")
    doctor = sub.add_parser("doctor", help="bounded read-only environment and prerequisite inspection")
    doctor.add_argument("--workspace", type=Path, default=Path.cwd())
    doctor.add_argument("--resource", help="inspect prerequisites for an available resource ID")
    doctor.add_argument("--version", help="exact revision; otherwise inspect the newest available revision")
    doctor.add_argument("--timeout", type=float, default=3, help="seconds per fixed probe (maximum 10)")
    resolution = sub.add_parser("resolve")
    resolution.add_argument("profile", help="local profile JSON path")
    resolution.add_argument("--target", required=True, help="JSON with observed target facts")
    resolution.add_argument("--pins", help="previous lock JSON; pins are preserved")
    resolution.add_argument("--overlay", help="explicit private local overlay JSON")
    resolution.add_argument("--output", type=Path, help="save only the resolved lock for later application")
    for verb in ("plan", "apply", "verify", "recover", "rollback", "remove"):
        command = sub.add_parser(verb)
        if verb in ("plan", "apply"):
            command.add_argument("lock", help="exact resolved lock JSON")
        if verb == "remove":
            command.add_argument("ids", nargs="+", help="installed resource IDs to remove")
        command.add_argument("--root", required=True, type=Path, help="target directory")
        command.add_argument("--state-dir", type=Path, help="override per-user state directory")
        if verb in ("apply", "recover", "rollback", "remove"):
            command.add_argument("--cache-dir", type=Path, help="override per-user verified content cache")
    sub.add_parser("generate")
    sub.add_parser("check")
    from xorder import downstream
    downstream.configure_check_parser(sub.add_parser("support-check", help="enforce release-group support using fresh policy and observed identities"))
    downstream.configure_fetch_parser(sub.add_parser("support-fetch", help="fetch an explicit 24-hour offline support policy snapshot"))
    args = parser.parse_args()
    if args.command in ("support-check", "support-fetch"):
        raise SystemExit(downstream.check_cli(args) if args.command == "support-check" else downstream.fetch_cli(args))
    if args.command == "generate":
        from library import generated
        for path, content in generated(args.repository_root).items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        return
    if args.command == "check":
        model.check(args.repository_root)
        return
    if args.command in ("plan", "apply", "verify", "recover", "rollback", "remove"):
        from xorder import apply as application
        common = {"root": args.root, "state_dir": args.state_dir}
        if args.command in ("apply", "recover", "rollback", "remove"):
            common["cache_dir"] = args.cache_dir
        if args.command in ("plan", "apply"):
            common["lock"] = model.read(args.lock)
            common["accepted_catalog"] = model.catalog(args.repository_root)
        if args.command == "remove":
            common["resource_ids"] = args.ids
        result = getattr(application, args.command)(**common)
        print(model.encoded(result), end="")
        if result["status"] not in ("ready", "applied", "unchanged", "passed", "recovered"):
            raise SystemExit(2)
        return
    cat = model.catalog(args.repository_root)
    if args.command == "doctor":
        from xorder.inspect import inspect_target
        resource = None
        if args.version and not args.resource:
            raise ValueError("doctor --version requires --resource")
        if args.resource:
            matches = [item for item in cat["resources"] if item["id"] == args.resource
                       and item["lifecycle"] == "available"
                       and (not args.version or item["version"] == args.version)]
            if not matches:
                raise ValueError("No available release matches the requested resource and revision")
            resource = max(matches, key=lambda item: model.version(item["version"]))
        result = inspect_target(args.workspace, resource, args.timeout)
        print(model.encoded(result), end="")
        if result["gaps"]:
            raise SystemExit(2)
        return
    if args.command == "list":
        entries = model.latest_resources(cat, include_unavailable=args.all) if args.latest else cat["resources"]
        result = {"schema_version": 2, "resources": [model.resource_summary(item) if args.summary else item for item in entries
                  if (not args.kind or item["kind"] == args.kind)
                  and (args.all or item["lifecycle"] == "available")]}
    elif args.command == "show":
        result = {"id": args.id, "resources": [item for item in cat["resources"] if item["id"] == args.id
                                               and (not args.version or item["version"] == args.version)]}
        if not result["resources"]:
            print(model.encoded({"status": "resource_unavailable", "id": args.id}), end="")
            raise SystemExit(2)
    else:
        profile = Path(args.profile)
        overlay = Path(args.overlay) if args.overlay else None
        result = resolve(model.read(profile), cat, model.read(args.target),
                         pins=model.read(args.pins) if args.pins else None,
                         overlay=model.read(overlay) if overlay else None,
                         profile_sha256=hashlib.sha256(profile.read_bytes()).hexdigest(),
                         overlay_sha256=hashlib.sha256(overlay.read_bytes()).hexdigest() if overlay else None,
                         root=args.repository_root)
        if args.output and result["status"] == "resolved":
            from xorder.apply import atomic_json
            atomic_json(args.output, result["lock"])
    print(model.encoded(result), end="")
    if result.get("status") == "resolution_failed":
        raise SystemExit(2)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, ValidationError) as error:
        print(model.encoded({"status": "error", "reason": str(error)}), end="")
        raise SystemExit(2)

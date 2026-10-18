#!/usr/bin/env python3
"""Apply real authored bundles through a controlled HTTPS candidate catalog.

The temporary records describe exercised candidates on a controlled fixture.
They are deleted with the fixture and never enter the repository's release ledger.
Runtime readiness and agent instruction following are separate acceptance concerns.
"""
import argparse
import contextlib
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import platform
import shutil
import ssl
import subprocess
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
from xorder import model
from xorder.release import public_artifact
from xorder.verify import prepare


def require(condition, reason):
    if not condition:
        raise RuntimeError(reason)


def observed_platform():
    machine = {"x86_64": "amd64", "aarch64": "arm64"}.get(platform.machine().lower(), platform.machine().lower())
    return platform.system().lower() + "/" + machine


@contextlib.contextmanager
def controlled_https(directory, temporary):
    """Trust a short-lived loopback server while retaining the system CA bundle."""
    certificate, key, trust = (temporary / name for name in ("server.pem", "server.key", "trust.pem"))
    subprocess.run([
        "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
        "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1",
        "-keyout", str(key), "-out", str(certificate),
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    system_ca = ssl.get_default_verify_paths().cafile
    require(system_ca and Path(system_ca).is_file(), "A system CA bundle is required for the controlled HTTPS fixture")
    trust.write_bytes(Path(system_ca).read_bytes() + b"\n" + certificate.read_bytes())
    requests = []

    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            super().do_GET()

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, directory=str(directory)))
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(certificate, key)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    previous = os.environ.get("SSL_CERT_FILE")
    os.environ["SSL_CERT_FILE"] = str(trust)
    try:
        yield f"https://localhost:{server.server_address[1]}", requests
    finally:
        if previous is None:
            os.environ.pop("SSL_CERT_FILE", None)
        else:
            os.environ["SSL_CERT_FILE"] = previous
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def cli(repository, command, *arguments, status):
    result = subprocess.run([
        sys.executable, str(ROOT / "scripts/xorder_cli.py"), "--repository-root", str(repository),
        command, *map(str, arguments),
    ], check=False, capture_output=True, text=True, cwd=ROOT)
    require(result.returncode in (0, 2), f"CLI failed unexpectedly: {result.stderr}")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"CLI did not return JSON: {result.stdout}\n{result.stderr}") from error
    require(value["status"] == status, f"Expected {command} status {status}, got {value}")
    require(result.returncode == (0 if status in ("resolved", "ready", "applied", "unchanged", "passed") else 2),
            f"CLI returned an incorrect exit code for {status}")
    return value


def snapshot(path):
    facts = path.stat()
    return path.read_bytes(), facts.st_mtime_ns, facts.st_ino, facts.st_mode & 0o777


def run_fixture(temporary):
    spec = model.read(ROOT / "tests/requirements/resource-application.json")
    require(observed_platform() == "linux/amd64", "This execution fixture is measured on linux/amd64")
    repository = temporary / "controlled-candidates"
    public = temporary / "server"
    public.mkdir()
    repository.mkdir()
    shutil.copytree(ROOT / "schemas", repository / "schemas")
    profile = ROOT / spec["profile"]
    source = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    definitions = model.definitions(ROOT)
    ids = spec["cases"][0]["expected_resources"]
    candidates = []
    for resource_id in ids:
        definition = definitions[resource_id]
        artifact, facts = prepare(definition, public, ROOT)
        candidates.append((definition, artifact, facts))

    # This fixture exercises file delivery. The required real native runtime has
    # its own gate; making that role optional only in this local overlay honestly
    # skips it because the controlled catalog has no environment release.
    overlay = temporary / "file-delivery-overlay.json"
    overlay.write_text(model.encoded({"roles": {"runtime": {"optional": True}}}))
    checked = []
    with controlled_https(public, temporary) as (url, requests):
        for definition, artifact, facts in candidates:
            publication = {**facts, "url": f"{url}/{artifact.name}"}
            command = public_artifact(definition, publication, temporary / "retrieved", ROOT)
            completed = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            evidence = f"{url}/controlled-fixture-evidence.json"
            # Metadata is created only after real trusted payload exercise passed.
            # Its scope stays this loopback fixture, never accepted publication.
            record = {
                "schema_version": 2, "id": definition["id"], "version": definition["revision"],
                "source_commit": source, "source_tag": f"{definition['id']}/v{definition['revision']}",
                "created_at": completed, "input_fingerprint": model.fingerprint(definition, ROOT),
                "lifecycle": "available", "definition": definition,
                "publication": {**publication, "public_download_verified_at": completed, "evidence": evidence},
                "verification": {"status": "passed", "surface": "controlled-fixture", "completed_at": completed,
                                 "evidence": evidence, "commands": [command]},
            }
            model.validate_record(record, ROOT)
            ledger = repository / "release-records/artifacts" / definition["id"] / f"{definition['revision']}.json"
            ledger.parent.mkdir(parents=True)
            ledger.write_text(model.encoded(record))
            checked.append({"id": definition["id"], "sha256": facts["sha256"], "surface": "controlled-fixture"})
        (public / "controlled-fixture-evidence.json").write_text(model.encoded({"scope": "controlled-fixture", "candidates": checked}))

        locks = {}
        for case in spec["cases"]:
            target = temporary / f"{case['name']}.target.json"
            target.write_text(model.encoded(case["target"]))
            lock = temporary / f"{case['name']}.lock.json"
            result = cli(repository, "resolve", profile, "--target", target, "--overlay", overlay, "--output", lock,
                         status="resolution_failed" if "expected_gap" in case else "resolved")
            if "expected_gap" in case:
                require(case["expected_gap"] in json.dumps(result["gaps"]), f"Missing expected consumer gap: {case['name']}")
                require(not lock.exists(), "A failed resolution must not save an applicable lock")
                continue
            actual_ids = sorted(item["id"] for item in result["lock"]["resources"])
            require(actual_ids == sorted(case["expected_resources"]), f"Wrong assignment for {case['name']}: {actual_ids}")
            locks[case["name"]] = lock

        state, cache, project = temporary / "state", temporary / "cache", temporary / "codex-project"
        project.mkdir()
        (project / "notes.txt").write_text("Unrelated project content\n")
        (project / "AGENTS.override.md").write_text("Existing project override stays owned by the project\n")
        before_unrelated = {name: snapshot(project / name) for name in ("notes.txt", "AGENTS.override.md")}
        common = ("--root", project, "--state-dir", state)
        cli(repository, "plan", locks["codex-project"], *common, status="ready")
        before_downloads = len(requests)
        cli(repository, "apply", locks["codex-project"], *common, "--cache-dir", cache, status="applied")
        require(len(requests) == before_downloads + len(ids), "Cold-cache apply must retrieve each exact candidate through HTTPS")
        for destination, expected_source in spec["files"].items():
            require((project / destination).read_bytes() == (ROOT / expected_source).read_bytes(),
                    f"Authored source/destination mismatch for {destination}")
        before = {name: snapshot(project / name) for name in spec["files"]}
        requests_before_repeat = len(requests)
        cli(repository, "apply", locks["codex-project"], *common, "--cache-dir", cache, status="unchanged")
        require(len(requests) == requests_before_repeat, "An unchanged repeat must not retrieve the payload again")
        require(before == {name: snapshot(project / name) for name in spec["files"]}, "Repeat touched managed files")
        require(before_unrelated == {name: snapshot(project / name) for name in before_unrelated}, "Unrelated project files were changed")
        require(cli(repository, "verify", *common, status="passed")["checked_files"] == 2, "Receipt must verify both managed files")

        other_project = temporary / "other-harness"
        other_project.mkdir()
        guidance = other_project / "AGENTS.md"
        guidance.write_text("Existing unowned guidance for another harness\n")
        saved = snapshot(guidance)
        cli(repository, "apply", locks["other-harness"], "--root", other_project, "--state-dir", state,
            "--cache-dir", cache, status="applied")
        require(snapshot(guidance) == saved, "An unselected context resource changed existing guidance")
        require((other_project / ".editorconfig").read_bytes() == (ROOT / spec["files"][".editorconfig"]).read_bytes(),
                "Other-harness formatting did not apply")

        conflict_project = temporary / "unowned-codex-guidance"
        conflict_project.mkdir()
        conflict = conflict_project / "AGENTS.md"
        conflict.write_text("Existing owner-selected instructions\n")
        saved = snapshot(conflict)
        cli(repository, "apply", locks["codex-project"], "--root", conflict_project, "--state-dir", state,
            "--cache-dir", cache, status="conflict")
        require(snapshot(conflict) == saved, "Conflicting unowned guidance was replaced")
        require(not (conflict_project / ".editorconfig").exists(), "A conflicted plan partially installed formatting")

    return {
        "status": "passed", "surface": "controlled-fixture", "platform": observed_platform(),
        "candidate_resources": checked,
        "checks": ["actual authored payloads packaged and verified after HTTPS retrieval", "CLI source/destination application",
                   "Codex project assignment and scope gaps", "unchanged repeat preserves bytes, timestamps and inode",
                   "unselected and unowned guidance preserved", "conflict prevents partial file installation"],
        "limits": ["temporary candidate catalog only; no accepted public release ledger changes",
                   "runtime environment and image readiness are checked separately", "no live-agent instruction-following claim"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="write the execution report for CI artifacts")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="xorder-application-consumer-") as directory:
        result = run_fixture(Path(directory))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(model.encoded(result))
    print(model.encoded(result), end="")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Qualify the locked prerelease Symfony project against real image tools."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import uuid


def run(command, *, cwd=None, accepted=(0,)):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=300)
    sys.stderr.write(result.stderr)
    if result.returncode not in accepted:
        sys.stderr.write(result.stdout)
        raise RuntimeError("Readiness command failed: " + repr(command))
    return result


def serena_symbols(project):
    spec = importlib.util.spec_from_file_location("mago_fixture_rpc", Path(__file__).parents[1] / "mago-serena/check.py")
    rpc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rpc)
    with rpc.RpcClient(["serena", "start-mcp-server", "--project", str(project), "--transport", "stdio",
                        "--agent-interface", "REPL", "--enable-web-dashboard", "false",
                        "--open-web-dashboard", "false", "--enable-gui-log-window", "false"], cwd=project) as client:
        rpc.mcp_initialize(client)
        instructions = rpc.tool(client, "initial_instructions")
        text = "\n".join(entry.get("text", "") for entry in instructions.get("content", []))
        session = instructions.get("structuredContent", {}).get("session_id")
        if not session:
            match = re.search(r"Your Serena session id is `([^`]+)`", text)
            assert match, instructions
            session = match[1]
        result = rpc.tool(client, "serena_repl", {"session": session, "code":
            "symbols = s.lsp.find_symbol('Greeting', relative_path='src/Service/Greeting.php', include_body=True)\n"
            "assert symbols, 'Symfony symbol lookup returned nothing'\n"
            "assert 'Symfony Mago development ready' in symbols.represent(), 'Source body absent'\n"
            "'XORDER_SYMFONY_SYMBOL_OK'"})
        assert "\n".join(entry.get("text", "") for entry in result.get("content", [])).strip() == "XORDER_SYMFONY_SYMBOL_OK", result


def inside():
    identity = json.loads(Path("/opt/xorder/image-identity.json").read_text())
    with tempfile.TemporaryDirectory(prefix="xorder-symfony-") as temporary:
        project = Path(temporary) / "app"
        base = ["library-symfony-mago", "--project", str(project)]
        run([*base, "init"])
        shutil.copyfile(Path(__file__).with_name("composer.lock"), project / "composer.lock")
        run(["composer", "install", "--no-interaction", "--no-progress", "--prefer-dist"], cwd=project)
        run([*base, "prepare"])
        run([*base, "check"])
        tools = run(["php", "vendor/bin/mate", "tools:list", "--format=json"], cwd=project)
        assert "symfony-profiler-list" in tools.stdout and "monolog-search" in tools.stdout, tools.stdout
        detail = run(["php", "vendor/bin/mate", "tools:call", "symfony-service-detail",
                      "--id=App\\Service\\Greeting", "--context=inspection-dev", "--format=json"], cwd=project)
        assert "Greeting" in detail.stdout, detail.stdout
        request = run(["php", "-r",
            "require 'vendor/autoload.php'; "
            "(new Symfony\\Component\\Dotenv\\Dotenv())->bootEnv('.env'); "
            "$kernel = new App\\Kernel('dev', true); "
            "$request = Symfony\\Component\\HttpFoundation\\Request::create('/?xorder=readiness'); "
            "$response = $kernel->handle($request); "
            "echo json_encode(['status'=>$response->getStatusCode(), 'body'=>$response->getContent(), "
            "'token'=>$response->headers->get('X-Debug-Token')]); "
            "$kernel->terminate($request, $response);"], cwd=project)
        response = json.loads(request.stdout)
        assert response["status"] == 200 and "Symfony Mago development ready" in response["body"], response
        assert re.fullmatch(r"[0-9a-f]{6}", response["token"]), response
        profiles = run(["php", "vendor/bin/mate", "tools:call", "symfony-profiler-list",
                        "--context=inspection-dev", "--limit=20", "--format=json"], cwd=project)
        assert response["token"] in profiles.stdout, profiles.stdout
        logs = run(["php", "vendor/bin/mate", "tools:call", "monolog-search", "--term=xorder Symfony readiness",
                    "--environment=dev", "--kernelContext=inspection-dev", "--limit=20", "--format=json"], cwd=project)
        assert "xorder Symfony readiness" in logs.stdout, logs.stdout
        for arguments in (["analyze", "--reporting-format", "json"], ["lint"],
                          ["format", "--check", "src"], ["guard", "--structural"]):
            run([*base, "native", "--", *arguments], cwd=project, accepted=(0, 1))
        graphs = []
        for control in ([], ["--extension-off"]):
            run([*base, "analyze", *control, "--"], cwd=project, accepted=(0, 1))
            folder = max((project / ".mago/evidence").glob("analyze-*"), key=lambda path: path.stat().st_mtime_ns)
            graphs.append(json.loads((folder / "graph.json").read_text()))
        assert graphs[0]["wiring_enabled"] is True and graphs[1]["wiring_enabled"] is False
        on = json.dumps(graphs[0]["symbols"]).lower()
        off = json.dumps(graphs[1]["symbols"]).lower()
        assert "monolog" in on and "monolog" not in off, (graphs[0], graphs[1])
        serena_symbols(project)
        source = project / "src/Service/Greeting.php"
        source.write_text(source.read_text() + "\n// freshness control\n")
        stale = run([*base, "check"], accepted=(3,))
        assert "stale" in stale.stderr.lower(), stale.stderr
    print(json.dumps({"status": "passed", "tuple": identity["lock"],
                      "checks": ["locked-prerelease-composer-install", "mate-discovery-and-compiled-context",
                                 "request-profiler-token-and-monolog-context",
                                 "native-mago-quality-commands", "wiring-on-off-graph-and-attestation",
                                 "serena-symfony-symbol-body", "stale-source-rejection"]}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", nargs="?")
    parser.add_argument("--inside", action="store_true")
    args = parser.parse_args()
    if args.inside:
        inside()
        return
    if not args.image:
        parser.error("Supply an image or --inside")
    root = Path(__file__).resolve().parents[3]
    folder = root / "out/symfony-mago"
    folder.mkdir(parents=True, exist_ok=True)
    name = "xorder-symfony-" + uuid.uuid4().hex
    command = [sys.executable, str(root / "scripts/container_network.py"), "docker", "run", "--rm", "--name", name,
               "--init", "-e", "PUID=1001", "-e", "PGID=1001", "-e", "CI=1",
               "-v", f"{root / 'tests/fixtures'}:/proof:ro"]
    ca = os.environ.get("CA_CERTIFICATE")
    if ca:
        command += ["-v", f"{ca}:/run/xorder-ca.pem:ro", "-e", "LIBRARY_CA_FILE=/run/xorder-ca.pem"]
    command += [args.image, "python3", "/proof/symfony-mago/check.py", "--inside"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=1200)
    finally:
        subprocess.run(["docker", "rm", "-f", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
    (folder / "acceptance.stderr").write_text(result.stderr)
    if result.returncode:
        sys.stderr.write(result.stderr[-20000:])
        raise SystemExit(result.returncode)
    record = json.loads(result.stdout)
    (folder / "acceptance.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record))


if __name__ == "__main__":
    main()

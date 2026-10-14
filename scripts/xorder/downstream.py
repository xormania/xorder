"""Fresh support policy and observed Docker identities for opted-in consumers."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request


DEFAULT_POLICY_URL = "https://raw.githubusercontent.com/xormania/xorder/master/lifecycle/release-groups.json"
POLICY_URLS = (DEFAULT_POLICY_URL, DEFAULT_POLICY_URL.replace("/master/", "/refs/heads/master/"))
MAX_BYTES = 2 * 1024 * 1024
TIMEOUT = 10
MAX_AGE = dt.timedelta(hours=24)
LOCK_NAME = "xorder-support.lock.json"


def utc_now():
    return dt.datetime.now(dt.timezone.utc)


def timestamp(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z", value):
        raise ValueError("Support timestamps must be UTC values ending in Z")
    try:
        return dt.datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise ValueError("Invalid support timestamp") from error


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def read_json(path):
    with Path(path).open("rb") as source:
        raw = source.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Support JSON exceeds the 2 MiB limit")
    try:
        return json.loads(raw)
    except (UnicodeError, ValueError) as error:
        raise ValueError("Support source is not valid UTF-8 JSON") from error


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        raise ValueError("Support policy redirects are refused; use the canonical public master URL")


def _fetch_policy_body(url):
    if url not in POLICY_URLS:
        raise ValueError("Support policy must use the canonical public xormania/xorder master URL")
    request = urllib.request.Request(url, headers={"User-Agent": "xorder-support-check", "Cache-Control": "no-cache"})
    opener = urllib.request.build_opener(_NoRedirect())
    deadline = time.monotonic() + TIMEOUT
    try:
        with opener.open(request, timeout=TIMEOUT) as response:
            if response.geturl() != url:
                raise ValueError("Support policy response changed its canonical URL")
            chunks, size = [], 0
            while True:
                if time.monotonic() >= deadline:
                    raise ValueError("Support policy fetch exceeded its read deadline")
                chunk = response.read1(min(65536, MAX_BYTES + 1 - size))
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
                if size > MAX_BYTES:
                    raise ValueError("Support policy exceeds the 2 MiB limit")
            policy = json.loads(b"".join(chunks))
    except (OSError, urllib.error.URLError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("Current support policy is unavailable; supply a valid explicitly refreshed offline snapshot") from error
    if not isinstance(policy, dict):
        raise ValueError("Support policy must be a JSON object")
    return policy


def fetch_snapshot(url=DEFAULT_POLICY_URL, *, now=None):
    """Use an owned worker so DNS, TLS and response reads have a wall deadline."""
    if url not in POLICY_URLS:
        raise ValueError("Support policy must use the canonical public xormania/xorder master URL")
    # Carry proxy routing and trust only; repository tokens and credential
    # configuration never enter the policy acquisition worker.
    network_keys = {"PATH", "SYSTEMROOT", "SSL_CERT_FILE", "SSL_CERT_DIR", "HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY", "NO_PROXY",
                    "https_proxy", "http_proxy", "all_proxy", "no_proxy"}
    environment = {key: value for key, value in os.environ.items() if key in network_keys}
    policy = _process_json([sys.executable, str(Path(__file__).resolve()), "__fetch_policy", url],
                           env=environment, label="Current support policy acquisition")
    if not isinstance(policy, dict):
        raise ValueError("Support policy must be a JSON object")
    fetched_at = now or utc_now()
    return {"schema_version": 1, "policy": policy, "receipt": {
        "url": url, "fetched_at": fetched_at.isoformat().replace("+00:00", "Z"),
        "valid_until": (fetched_at + MAX_AGE).isoformat().replace("+00:00", "Z"),
        "policy_sha256": hashlib.sha256(encoded(policy)).hexdigest()}}


def load_policy(*, policy_file=None, policy_url=None, now=None):
    if policy_file and policy_url:
        raise ValueError("Choose one current policy URL or one offline policy snapshot")
    now = now or utc_now()
    snapshot = read_json(policy_file) if policy_file else fetch_snapshot(policy_url or DEFAULT_POLICY_URL)
    if not isinstance(snapshot, dict) or snapshot.get("schema_version") != 1 or not isinstance(snapshot.get("policy"), dict):
        raise ValueError("Offline policy requires a support-fetch snapshot with a receipt; a bare checkout policy is insufficient")
    receipt = snapshot.get("receipt")
    if not isinstance(receipt, dict) or receipt.get("url") not in POLICY_URLS:
        raise ValueError("Policy snapshot has no canonical acquisition receipt")
    if receipt.get("policy_sha256") != hashlib.sha256(encoded(snapshot["policy"])).hexdigest():
        raise ValueError("Policy snapshot content does not match its acquisition receipt")
    fetched, valid_until = timestamp(receipt.get("fetched_at")), timestamp(receipt.get("valid_until"))
    if fetched > now or not fetched < valid_until <= fetched + MAX_AGE or now >= valid_until:
        raise ValueError("Support policy snapshot is expired or has invalid freshness dates; refresh it with support-fetch")
    return snapshot["policy"], receipt["fetched_at"], receipt


def _process_json(argv, env=None, label="Support observation"):
    """Bound one observation and only the subprocess group it owns."""
    if os.name != "posix":
        raise ValueError(label + " requires a POSIX host such as Linux/WSL")
    deadline = time.monotonic() + TIMEOUT
    process = subprocess.Popen(argv, env=env, start_new_session=True, bufsize=0,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    timeout_message = label + " timed out; restore the selected engine/network or provide a current offline snapshot"
    try:
        stdout, received = bytearray(), 0
        with selectors.DefaultSelector() as selector:
            for pipe, stream in ((process.stdout, "stdout"), (process.stderr, "stderr")):
                os.set_blocking(pipe.fileno(), False)
                selector.register(pipe, selectors.EVENT_READ, stream)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ValueError(timeout_message)
                ready = selector.select(remaining)
                if not ready:
                    raise ValueError(timeout_message)
                for key, _ in ready:
                    # Read at most one byte beyond the combined budget. stderr
                    # counts against the same cap but is never retained/logged.
                    try:
                        chunk = os.read(key.fd, min(65536, MAX_BYTES - received + 1))
                    except BlockingIOError:
                        continue
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    received += len(chunk)
                    if received > MAX_BYTES:
                        raise ValueError(label + " exceeds the combined 2 MiB stdout/stderr limit")
                    if key.data == "stdout":
                        stdout.extend(chunk)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ValueError(timeout_message)
            try:
                process.wait(timeout=remaining)
            except subprocess.TimeoutExpired as error:
                raise ValueError(timeout_message) from error
        if process.returncode:
            raise ValueError(label + " failed; restore access or pull the selected digest before retrying")
        return json.loads(stdout)
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.stdout.close()
        process.stderr.close()
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            pass


def _docker(argv, env=None):
    return _process_json(["docker", *argv], env, "Support Docker observation")


def _repository(reference):
    if not isinstance(reference, str) or not re.fullmatch(r"[a-z0-9][a-z0-9./:_@+-]*", reference):
        raise ValueError("Support observation needs an explicit Docker image reference")
    reference = reference.split("@", 1)[0]
    prefix, _, leaf = reference.rpartition("/")
    return (prefix + "/" if prefix else "") + leaf.split(":", 1)[0]


def _registry_repository(reference):
    """Parse the whole registry reference; owner namespaces are not ownership."""
    if not isinstance(reference, str) or reference.split("/", 2)[:2] != ["ghcr.io", "xormania"]:
        return None
    component = r"[a-z0-9]+(?:(?:[._]|__|-+)[a-z0-9]+)*"
    match = re.fullmatch(r"(?P<repository>ghcr\.io/xormania/" + component + r"(?:/" + component + r")*)"
                         r"(?::[A-Za-z0-9_][A-Za-z0-9_.-]{0,127})?(?:@sha256:[a-f0-9]{64})?", reference)
    if match is None:
        raise ValueError("Selected GHCR image must use a valid complete repository, tag or digest reference")
    return match["repository"]


def known_image_repositories(policy=None, *, root=None):
    """Recognize published xorder packages, including historical group members."""
    root = Path(root or Path(__file__).resolve().parents[2])
    known = set()
    def members(group):
        for member in group.get("resources", []):
            repository = _registry_repository(member.get("identity"))
            if repository:
                known.add(repository)
    if policy is None:
        policy_path = root / "lifecycle/release-groups.json"
        policy = read_json(policy_path) if policy_path.is_file() else {}
    for group in policy.get("groups", []):
        members(group)
    bootstrap = root / "lifecycle/bootstrap-group.json"
    if bootstrap.is_file():
        members(read_json(bootstrap))
    # Availability changes do not erase package ownership. Retain every local
    # accepted image record, including deprecated/withdrawn revisions.
    for path in (root / "release-records").glob("*/*/*.json"):
        item = read_json(path)
        if (item.get("verification", {}).get("status") == "passed"
                and item.get("publication", {}).get("public_pull_verified_at")):
            repository = _registry_repository(item["publication"].get("repository"))
            if repository:
                known.add(repository)
    return known


def _identity(entry, inspected, repository):
    if not isinstance(inspected, dict):
        raise ValueError("Docker did not return an observed image identity")
    matches = [ref for ref in inspected.get("RepoDigests") or []
               if isinstance(ref, str) and re.fullmatch(re.escape(repository) + r"@sha256:[0-9a-f]{64}", ref)]
    if not matches:
        raise ValueError("Image has no observed repository digest; pull its locked published digest before checking support")
    expected = entry.get("identity")
    # One local image can have references to several manifest indexes. Prefer
    # the locked identity if the engine actually reports it, never invent it.
    identity = expected if expected in matches else sorted(matches)[0]
    os_name, architecture = inspected.get("Os"), inspected.get("Architecture")
    if not os_name or not architecture:
        raise ValueError("Docker did not report the selected image platform")
    observed = {"line_id": entry.get("line_id"), "identity": identity,
                "platform": os_name + "/" + architecture}
    if entry.get("service"):
        observed["service"] = entry["service"]
    return observed


def _resources(lock):
    resources = lock.get("resources", []) if isinstance(lock, dict) else None
    if not isinstance(resources, list) or not resources or not all(isinstance(entry, dict) for entry in resources):
        raise ValueError("Support lock must declare a nonempty resources list of objects")
    return resources


def observe_images(lock, selections, *, env=None):
    """Inspect selected/cached images; aliases are inputs, RepoDigests are facts."""
    observed = []
    resources = _resources(lock)
    keys = [entry.get("service") or entry.get("line_id") for entry in resources]
    if len(set(keys)) != len(keys) or None in keys:
        raise ValueError("Support lock needs unique service or line_id observation keys")
    for key, entry in zip(keys, resources):
        reference = selections.get(key)
        if not reference:
            raise ValueError("No actual selected image was supplied for " + key)
        repository = _repository(reference)
        images = _docker(["image", "inspect", "--", reference], env)
        if not isinstance(images, list) or len(images) != 1:
            raise ValueError("Docker image observation did not identify one selected image")
        observed.append(_identity(entry, images[0], repository))
    return observed


def observe_containers(lock, containers, *, env=None):
    observed = []
    for entry in _resources(lock):
        service = entry.get("service")
        if not service:
            raise ValueError("Runner support locks must map every resource to its Compose service")
        matches = [container for container in containers
                   if container.get("Config", {}).get("Labels", {}).get("com.docker.compose.service") == service
                   and container.get("State", {}).get("Running")]
        if len(matches) != 1 or not matches[0].get("Image"):
            raise ValueError("No unique running image identity is available for Compose service " + service)
        image_id = matches[0]["Image"]
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
            raise ValueError("Container did not report a content-addressed Docker image ID")
        images = _docker(["image", "inspect", "--", image_id], env)
        if not isinstance(images, list) or len(images) != 1:
            raise ValueError("Docker did not return the running container's image")
        observed.append(_identity(entry, images[0], _repository(entry.get("identity"))))
    if not observed:
        raise ValueError("Runner support lock has no observed resources")
    return observed


def check(lock, observed, *, policy_file=None, policy_url=None, now=None, policy_context=None):
    from release_groups import check_selection
    policy, fetched_at, receipt = policy_context or load_policy(policy_file=policy_file, policy_url=policy_url, now=now)
    result = check_selection(policy, lock, observed, now=now, fetched_at=fetched_at)
    result["policy_receipt"] = receipt
    result["observed"] = observed
    return result


def adopted_lock(workspace, env):
    explicit = env.get("XORDER_SUPPORT_LOCK")
    if explicit:
        path = Path(explicit)
        return path if path.is_absolute() else Path(workspace) / path
    path = Path(workspace) / LOCK_NAME
    return path if path.is_file() else None


def announced_rollout():
    path = Path(__file__).resolve().parents[2] / "lifecycle/release-groups.json"
    if not path.is_file():
        return None
    policy = read_json(path)
    from release_groups import validate_policy
    validate_policy(policy)
    return policy["legacy"]["enforce_after"]


def requires_check(workspace, env):
    return bool(env.get("XORDER_SOURCE_VALIDATION_PROOF")) or adopted_lock(workspace, env) is not None or announced_rollout() is not None


def _report_result(result):
    for warning in result.get("warnings", []):
        print("xorder support warning: " + warning.get("message", warning.get("code", "warning")), flush=True)
        if warning.get("action"):
            print(warning["action"], flush=True)
    if not result.get("ok"):
        details = "; ".join(error.get("message", error.get("code", "unsupported")) +
                            (" " + error["action"] if error.get("action") else "")
                            for error in result.get("errors", []))
        raise ValueError("Downstream image support failed: " + (details or result.get("code", "unsupported")))
    return result


def source_validation_check(observed, proof):
    """Validate builder-owned local image IDs for an explicit upstream test scope.

    This is a hook for xorder's source build fixture, not an environment-variable
    bypass. Ordinary downstream runner calls never supply this proof.
    """
    if (not isinstance(proof, dict) or set(proof) != {"scope", "source_commit", "images"}
            or proof["scope"] != "xorder-source-validation"
            or not isinstance(proof["source_commit"], str)
            or not re.fullmatch(r"[a-f0-9]{40}", proof["source_commit"])):
        raise ValueError("Upstream source validation requires an explicit builder provenance proof")
    def identities(entries):
        if not isinstance(entries, list) or not entries:
            raise ValueError("Source validation needs actual selected image IDs")
        result = {}
        for entry in entries:
            if (not isinstance(entry, dict) or set(entry) != {"service", "image_id"}
                    or not isinstance(entry["service"], str) or not entry["service"]
                    or not isinstance(entry["image_id"], str)
                    or not re.fullmatch(r"sha256:[a-f0-9]{64}", entry["image_id"])
                    or entry["service"] in result):
                raise ValueError("Source validation images must uniquely map services to observed image IDs")
            result[entry["service"]] = entry["image_id"]
        return result
    if identities(observed) != identities(proof["images"]):
        raise ValueError("Selected source-validation image IDs differ from builder provenance")
    return {"ok": True, "status": "source_validation", "scope": proof["scope"],
            "source_commit": proof["source_commit"], "observed": observed, "errors": [], "warnings": []}


def source_commit(root=None):
    root = Path(root or Path(__file__).resolve().parents[2])
    value = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True, timeout=TIMEOUT).strip()
    if not re.fullmatch(r"[a-f0-9]{40}", value):
        raise ValueError("Source validation requires the validating checkout's exact commit")
    return value


def observe_source_images(selections, *, env=None):
    observed = []
    for service, reference in sorted(selections.items()):
        _repository(reference)  # Validate one literal image argument, including local IDs.
        facts = _docker(["image", "inspect", "--", reference], env)
        if not isinstance(facts, list) or len(facts) != 1:
            raise ValueError("Source fixture needs one observed image per service")
        observed.append({"service": service, "image_id": facts[0].get("Id")})
    return observed


def write_source_proof(path, observed, source):
    proof = {"scope": "xorder-source-validation", "source_commit": source, "images": observed}
    source_validation_check(observed, proof)
    path = Path(path)
    path.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n")
    path.chmod(0o600)
    return proof


def prepare_fixture_proof(builder_path, selections, output, *, root=None, env=None):
    """Trusted fixture adapter adds a pinned companion before project hooks run."""
    proof = read_json(builder_path)
    source_validation_check(proof.get("images") if isinstance(proof, dict) else None, proof)
    if proof["source_commit"] != source_commit(root):
        raise ValueError("Builder proof belongs to another validating xorder checkout")
    observed = observe_source_images(selections, env=env)
    declared = {entry["service"]: entry["image_id"] for entry in proof["images"]}
    actual = {entry["service"]: entry["image_id"] for entry in observed}
    if any(actual.get(service) != image_id for service, image_id in declared.items()):
        raise ValueError("Fixture candidate differs from builder-owned validation image")
    if not declared or set(actual) != {"php", "browser"}:
        raise ValueError("UXor source proof must bind exactly its PHP and browser services")
    return write_source_proof(output, observed, proof["source_commit"])


def _runner_source_check(workspace, env, *, configuration=None, containers=None, prepared=None):
    path = Path(env["XORDER_SOURCE_VALIDATION_PROOF"])
    if path.is_symlink() or not path.is_file() or path.resolve().is_relative_to(Path(workspace).resolve()):
        raise ValueError("Source validation proof must be an existing regular file outside the consumer workspace")
    proof = prepared["proof"] if prepared and prepared.get("source_validation") else read_json(path)
    source_validation_check(proof.get("images") if isinstance(proof, dict) else None, proof)
    if proof["source_commit"] != source_commit():
        raise ValueError("Source proof does not match the validating xorder checkout")
    expected = {entry["service"] for entry in proof["images"]}
    if expected != {"php", "browser"}:
        raise ValueError("Runner source-validation proof must bind exactly the PHP and browser services")
    if configuration is not None:
        services = configuration.get("services", {})
        known = known_image_repositories()
        for service, item in services.items():
            if _registry_repository(item.get("image")) in known and service not in expected:
                raise ValueError("Source validation proof omits selected xorder service " + service)
        selected = {service: services.get(service, {}).get("image") for service in expected}
        observed = observe_source_images(selected, env=env)
    else:
        observed = []
        for service in sorted(expected):
            matches = [container for container in containers or []
                       if container.get("Config", {}).get("Labels", {}).get("com.docker.compose.service") == service
                       and container.get("State", {}).get("Running")]
            if len(matches) != 1:
                raise ValueError("No unique running source-validation service " + service)
            observed.append({"service": service, "image_id": matches[0].get("Image")})
    return source_validation_check(observed, proof)


def runner_precheck(workspace, env, configuration):
    """Check declared support before pulling; actual content follows the pull."""
    if env.get("XORDER_SOURCE_VALIDATION_PROOF"):
        _runner_source_check(workspace, env, configuration=configuration)
        return {"source_validation": True, "proof": read_json(env["XORDER_SOURCE_VALIDATION_PROOF"]), "services": []}
    path = adopted_lock(workspace, env)
    if path is None:
        runner_check(workspace, env)
        return None
    lock = read_json(path)
    context = load_policy(policy_file=env.get("XORDER_SUPPORT_POLICY_FILE"),
                          policy_url=env.get("XORDER_SUPPORT_POLICY_URL"))
    from release_groups import check_selection
    result = check_selection(context[0], lock, [], fetched_at=context[1])
    result["errors"] = [error for error in result["errors"] if error["code"] != "actual-image-missing"]
    result["ok"] = not result["errors"]
    result["code"] = "selection-prechecked" if result["ok"] else result["errors"][0]["code"]
    _report_result(result)
    services = configuration.get("services", {})
    expected_services = [entry.get("service") for entry in lock["resources"]]
    if None in expected_services or len(set(expected_services)) != len(expected_services):
        raise ValueError("Runner support locks must uniquely map resources to their Compose services")
    for entry in lock["resources"]:
        image = services.get(entry["service"], {}).get("image")
        if not image or _repository(image) != _repository(entry["identity"]):
            raise ValueError("Configured image repository differs from support lock for " + entry["service"])
        if "@" in image:
            member = next(member for group in context[0]["groups"] if group["id"] == lock["group"]
                          for member in group["resources"] if member["line_id"] == entry["line_id"])
            allowed = {entry["identity"], _repository(entry["identity"]) + "@" +
                       next(platform["digest"] for platform in member["platforms"] if platform["platform"] == entry["platform"])}
            if image not in allowed:
                raise ValueError("Configured image digest differs from support lock for " + entry["service"])
    known = known_image_repositories(context[0])
    for service, value in services.items():
        if _registry_repository(value.get("image")) in known and service not in expected_services:
            raise ValueError("Selected xorder image service is missing from support lock: " + service)
    return {"lock": lock, "policy_context": context, "services": expected_services}


def runner_check(workspace, env, *, configuration=None, containers=None, prepared=None):
    """Enforce adopted groups and the separately announced legacy migration date."""
    if env.get("XORDER_SOURCE_VALIDATION_PROOF"):
        return _runner_source_check(workspace, env, configuration=configuration, containers=containers, prepared=prepared)
    path = adopted_lock(workspace, env)
    if path is None:
        if announced_rollout() is None:
            return {"ok": True, "status": "not_adopted", "warnings": [], "errors": []}
        policy, _, receipt = load_policy(policy_file=env.get("XORDER_SUPPORT_POLICY_FILE"),
                                        policy_url=env.get("XORDER_SUPPORT_POLICY_URL"))
        from release_groups import validate_policy
        validate_policy(policy)
        deadline = policy["legacy"]["enforce_after"]
        if deadline is None:
            return {"ok": True, "status": "not_adopted", "warnings": [], "errors": [], "policy_receipt": receipt}
        expired = utc_now() >= timestamp(deadline)
        item = {"code": "support_lock_required", "message": "Project has no release-group support lock; adoption deadline " + deadline,
                "action": "Select an accepted group, validate project behavior, and commit xorder-support.lock.json; see docs/downstream-support.md"}
        return _report_result({"ok": not expired, "status": "unsupported" if expired else "migration_required",
                               "warnings": [] if expired else [item], "errors": [item] if expired else [], "policy_receipt": receipt})
    lock = prepared["lock"] if prepared else read_json(path)
    if not isinstance(lock, dict):
        raise ValueError("Support lock must be a JSON object")
    context = prepared["policy_context"] if prepared else load_policy(
        policy_file=env.get("XORDER_SUPPORT_POLICY_FILE"), policy_url=env.get("XORDER_SUPPORT_POLICY_URL"))
    if configuration is not None:
        services = configuration.get("services", {})
        declared = {entry.get("service") for entry in _resources(lock)}
        if None in declared:
            raise ValueError("Runner support locks must map every resource to its Compose service")
        known = known_image_repositories(context[0])
        for service, value in services.items():
            if _registry_repository(value.get("image")) in known and service not in declared:
                raise ValueError("Selected xorder image service is missing from support lock: " + service)
        selected = {service: value.get("image") for service, value in services.items()}
        observed = observe_images(lock, selected, env=env)
    else:
        observed = observe_containers(lock, containers or [], env=env)
    result = check(lock, observed, policy_file=env.get("XORDER_SUPPORT_POLICY_FILE"),
                   policy_url=env.get("XORDER_SUPPORT_POLICY_URL"),
                   policy_context=context)
    return _report_result(result)


def configure_check_parser(parser):
    parser.add_argument("--lock", required=True, type=Path, help="project release-group support lock")
    policy = parser.add_mutually_exclusive_group()
    policy.add_argument("--policy-url", help="canonical current public policy URL; fetched on every check")
    policy.add_argument("--policy-file", type=Path, help="explicit offline support-fetch snapshot, valid at most 24 hours")
    actual = parser.add_mutually_exclusive_group(required=True)
    actual.add_argument("--actual", type=Path, help="JSON list of actual image identities collected by your CI engine")
    actual.add_argument("--image", action="append", metavar="SERVICE=REFERENCE", help="inspect a selected/cached Docker image; repeat for every lock entry")


def configure_fetch_parser(parser):
    parser.add_argument("--policy-url", default=DEFAULT_POLICY_URL)
    parser.add_argument("--output", required=True, type=Path, help="save an explicitly refreshed offline snapshot")


def check_cli(args):
    lock = read_json(args.lock)
    if not isinstance(lock, dict):
        raise ValueError("Support lock must be a JSON object")
    if args.actual:
        observed = read_json(args.actual)
        if not isinstance(observed, list):
            raise ValueError("Actual support identities must be a JSON list")
    else:
        selections = {}
        for selection in args.image:
            key, separator, reference = selection.partition("=")
            if not separator or not key or not reference or key in selections:
                raise ValueError("Each --image needs one unique SERVICE=REFERENCE")
            selections[key] = reference
        observed = observe_images(lock, selections)
    result = check(lock, observed, policy_file=args.policy_file, policy_url=args.policy_url)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 2


def fetch_cli(args):
    snapshot = fetch_snapshot(args.policy_url)
    # A malformed fetched policy never becomes an explicitly trusted snapshot.
    from release_groups import validate_policy
    validate_policy(snapshot["policy"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name("." + args.output.name + ".tmp-" + str(os.getpid()))
    try:
        temporary.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
        temporary.replace(args.output)
    finally:
        temporary.unlink(missing_ok=True)
    print(json.dumps({"status": "policy_fetched", "output": str(args.output), "receipt": snapshot["receipt"]}, indent=2))
    return 0


def main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    configure_check_parser(commands.add_parser("check", help="check a selected group against current policy and actual images"))
    configure_fetch_parser(commands.add_parser("fetch", help="prepare a 24-hour offline policy snapshot"))
    args = parser.parse_args(arguments)
    return check_cli(args) if args.command == "check" else fetch_cli(args)


if __name__ == "__main__":
    # The direct entry point is stdlib-only; the general discovery CLI also
    # exposes support-check and support-fetch for existing xorder consumers.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    try:
        if len(sys.argv) == 3 and sys.argv[1] == "__fetch_policy":
            print(json.dumps(_fetch_policy_body(sys.argv[2])))
            raise SystemExit(0)
        raise SystemExit(main())
    except (ValueError, OSError, KeyError) as error:
        print(json.dumps({"ok": False, "status": "unsupported", "code": "support_check_failed", "reason": str(error)}))
        raise SystemExit(2)

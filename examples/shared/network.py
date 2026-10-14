#!/usr/bin/env python3
"""Container proxy settings, kept separate from the host command environment."""
import ipaddress
import json
import os
import signal
import subprocess
import sys
import uuid
from urllib.parse import urlsplit, urlunsplit

from proxy_relay import OWNER_LABEL, ensure, owner_label, stop
from runtime import docker_observation

PROXIES = ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy")


def local_engine(env):
    context = env.get("DOCKER_CONTEXT")
    endpoint = env.get("DOCKER_HOST") if not context else None
    if not endpoint:
        command = ["docker", "context", "inspect"] + ([context] if context else [])
        endpoint = json.loads(docker_observation(
            [*command[1:], "--format", "{{json .Endpoints.docker.Host}}"], env))
    return isinstance(endpoint, str) and endpoint.startswith(("unix://", "npipe://"))


def bridge_address(env):
    if not local_engine(env):
        raise ValueError("Loopback proxy forwarding needs the proxy and Docker bridge on this host; "
                         "configure a container-reachable proxy for the remote engine")
    networks = json.loads(docker_observation(["network", "inspect", "bridge"], env))
    for config in networks[0]["IPAM"]["Config"]:
        address = config.get("Gateway", "")
        if address and ipaddress.ip_address(address).version == 4:
            return address
    raise ValueError("Docker has no IPv4 bridge gateway reachable from this host; configure a container-reachable proxy")


def loopback_proxy(value, key):
    try:
        parsed = urlsplit(value if "://" in value else "http://" + value)
        host = parsed.hostname or ""
        loopback = host.rstrip(".").lower() == "localhost"
        try:
            address = ipaddress.ip_address(host)
            loopback |= address.is_loopback or bool(address.version == 6 and address.ipv4_mapped and address.ipv4_mapped.is_loopback)
        except ValueError:
            pass
        if not loopback:
            return None
        defaults = {"http": 80, "https": 443, "socks5": 1080, "socks5h": 1080, "socks4": 1080, "socks4a": 1080}
        port = parsed.port or defaults.get(parsed.scheme)
        if not port:
            raise ValueError("Missing port")
        return parsed, host, port
    except ValueError as error:
        raise ValueError(f"Invalid {key} URL (value redacted)") from error


def container_environment(env, owner, *, reconfigure=False, services=()):
    mode = env.get("PROXY_PASSTHROUGH", "auto")
    if mode not in ("auto", "0", "1"):
        raise ValueError("PROXY_PASSTHROUGH must be auto, 0 (disable), or 1 (forward unchanged)")
    result = {key: env.get(key, "") if mode != "0" else "" for key in PROXIES}
    pending = {key: proxy for key, value in result.items()
               if mode == "auto" and value and (proxy := loopback_proxy(value, key))}
    if pending:
        bind = bridge_address(env)
        targets = sorted({(host, port) for _, host, port in pending.values()})
        ports = ensure(owner, bind, targets, reconfigure=reconfigure, env=env)
        for key, (parsed, host, port) in pending.items():
            credentials = parsed.netloc.rsplit("@", 1)[0] + "@" if "@" in parsed.netloc else ""
            # A numeric bridge address also works when container DNS is unavailable.
            result[key] = urlunsplit(parsed._replace(netloc=credentials + bind + ":" + str(ports[targets.index((host, port))])))
    elif reconfigure:
        stop(owner)
    for key, other in (("NO_PROXY", "no_proxy"), ("no_proxy", "NO_PROXY")):
        entries = [entry.strip() for entry in env.get(key, env.get(other, "")).split(",") if entry.strip()]
        result[key] = ",".join(dict.fromkeys([*entries, "localhost", "127.0.0.1", "::1", *services]))
    return result


def main(arguments):
    # Toolkit uses an ephemeral docker run; Uxor owns a persistent relay.
    if arguments[:2] != ["docker", "run"]:
        raise ValueError("Usage: network.py docker run [ARGS...]")
    owner = "run:" + uuid.uuid4().hex
    try:
        env = dict(os.environ)
        container = container_environment(env, owner)
        flags = ["--label", OWNER_LABEL + "=" + owner_label(owner)]
        flags += [part for key, value in container.items() for part in ("-e", key + "=" + value)]
        command = arguments[:2] + flags + arguments[2:]
        return subprocess.call(command, env=env)
    finally:
        stop(owner)


if __name__ == "__main__":
    def terminate(signum, _frame):
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, terminate)
    try:
        sys.exit(main(sys.argv[1:]))
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"xorder network: {error}", file=sys.stderr)
        sys.exit(64)

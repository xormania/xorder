#!/usr/bin/env python3
"""Keep host proxies separate from bridge-container proxy configuration."""
import ipaddress
import os
import subprocess
import sys
from urllib.parse import urlsplit

PROXIES = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY")


def is_loopback(value):
    parsed = urlsplit(value if "://" in value else "http://" + value)
    host = (parsed.hostname or "").rstrip(".").lower()
    if host == "localhost":
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.is_loopback or bool(
        address.version == 6 and address.ipv4_mapped and address.ipv4_mapped.is_loopback)


def container_proxies(environment):
    result = {}
    for upper in PROXIES:
        override = "CONTAINER_" + upper
        for key in (upper, upper.lower()):
            value = environment.get(override, environment.get(key, environment.get(upper, "")))
            if upper != "NO_PROXY" and value:
                try:
                    loopback = is_loopback(value)
                except ValueError as error:
                    raise ValueError(f"Invalid {override if override in environment else key} URL (value redacted)") from error
                if loopback:
                    if override in environment:
                        raise ValueError(f"{override} must be container-reachable or empty for direct egress")
                    print(f"xorder network: ignoring host {key} loopback proxy inside the container; "
                          f"set {override} to a reachable proxy if direct egress is unavailable", file=sys.stderr)
                    value = ""
            result[key] = value
    return result


def main(arguments):
    if arguments[:2] not in (["docker", "run"], ["docker", "compose"]):
        raise ValueError("Usage: container_network.py docker {run|compose} [ARGS...]")
    environment = dict(os.environ)
    proxies = container_proxies(environment)
    if arguments[1] == "run":
        flags = [part for key, value in proxies.items() for part in ("-e", key + "=" + value)]
        arguments = arguments[:2] + flags + arguments[2:]
    else:
        # Compose interpolation uses these names; the Docker client and daemon
        # keep their host proxy configuration.
        environment.update({"CONTAINER_" + key: value for key, value in proxies.items()})
    return subprocess.call(arguments, env=environment)


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except (ValueError, OSError) as error:
        print(f"xorder network: {error}", file=sys.stderr)
        sys.exit(64)

#!/usr/bin/env python3
"""OCI digest resolution with explicit 404 handling and optional GHCR credentials."""
import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request

ACCEPT = ", ".join(["application/vnd.oci.image.index.v1+json", "application/vnd.docker.distribution.manifest.list.v2+json",
                    "application/vnd.oci.image.manifest.v1+json", "application/vnd.docker.distribution.manifest.v2+json"])


def resolve(reference, authenticated=False):
    registry, rest = reference.split("/", 1)
    repository, separator, tag = rest.partition("@")
    if not separator:
        repository, tag = rest.rsplit(":", 1)
    host = "registry-1.docker.io" if registry == "docker.io" else registry
    auth = "https://auth.docker.io/token" if registry == "docker.io" else f"https://{host}/token"
    service = "registry.docker.io" if registry == "docker.io" else host
    scope = "pull,push" if authenticated else "pull"
    query = urllib.parse.urlencode({"service": service, "scope": f"repository:{repository}:{scope}"})
    req = urllib.request.Request(auth + "?" + query)
    if authenticated and registry == "ghcr.io":
        credentials = f"{os.environ['GITHUB_ACTOR']}:{os.environ['GH_TOKEN']}".encode()
        # Registry redirects must never forward the account credential.
        req.add_unredirected_header("Authorization", "Basic " + base64.b64encode(credentials).decode())
    # The token endpoint is constructed with HTTPS for every registry.
    with urllib.request.urlopen(req, timeout=60) as response:  # nosec B310
        body = json.load(response)
        token = body.get("token") or body["access_token"]
    req = urllib.request.Request(f"https://{host}/v2/{repository}/manifests/{tag}", headers={"Accept": ACCEPT})
    # Pull/push bearer tokens are also scoped to the initial registry request.
    req.add_unredirected_header("Authorization", "Bearer " + token)
    try:
        # The manifest endpoint is constructed with HTTPS above.
        with urllib.request.urlopen(req, timeout=60) as response:  # nosec B310
            body = json.load(response)
            digest = response.headers["Docker-Content-Digest"]
            platforms = {m["platform"]["os"] + "/" + m["platform"]["architecture"]: m["digest"] for m in body.get("manifests", []) if m.get("platform", {}).get("os") != "unknown"}
            return {"digest": digest, "platforms": platforms}
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        # Authentication, outages and rate limits must never look like an absent tag.
        raise

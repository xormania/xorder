#!/usr/bin/env python3
"""Pass only additional, unique validated roots to Debian's trust updater."""
import hashlib
from pathlib import Path
import re
import subprocess
import sys


def certificates(text):
    pattern = re.compile(r"-----BEGIN CERTIFICATE-----\s+.*?-----END CERTIFICATE-----", re.S)
    matches = list(pattern.finditer(text))
    remainder = pattern.sub("", text)
    if not matches or any(line.strip() and not line.lstrip().startswith("#") for line in remainder.splitlines()):
        raise ValueError("CA bundle must contain valid PEM certificates and whitespace/comments only")
    for match in matches:
        cert = match.group() + "\n"
        der = subprocess.check_output(["openssl", "x509", "-outform", "DER"], input=cert.encode(), stderr=subprocess.PIPE)
        yield hashlib.sha256(der).hexdigest(), cert


def additional(bundle, system):
    known = set()
    for path in system.rglob("*.crt"):
        for digest, _ in certificates(path.read_text()):
            known.add(digest)
    result = []
    for digest, cert in certificates(bundle):
        if digest not in known:
            result.append(cert)
            known.add(digest)
    return "".join(result)


if __name__ == "__main__":
    try:
        result = additional(Path(sys.argv[1]).read_text(), Path("/usr/share/ca-certificates"))
        Path(sys.argv[2]).write_text(result)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print("Proxy trust: " + str(error), file=sys.stderr)
        raise SystemExit(64)

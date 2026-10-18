#!/usr/bin/env bash
# Runs the public readiness recipe on a disposable real consuming project.
set -euo pipefail
line=${1:?Usage: verify-image.sh LINE_ID IMAGE}
image=${2:?Supply image reference}
root=$(cd "$(dirname "$0")/.." && pwd)
if [[ -n "${CA_CERTIFICATE:-}" ]]; then
  [[ "$CA_CERTIFICATE" = /* && -f "$CA_CERTIFICATE" && -r "$CA_CERTIFICATE" ]] || { echo 'CA_CERTIFICATE must be a readable absolute PEM file' >&2; exit 64; }
fi
family=${line%%/*}
if [[ "$family" = playwright-browser ]]; then
  work=$(mktemp -d)
  trap 'rm -rf "$work"' EXIT
  mkdir -p "$root/out/playwright"
  docker run --rm --network=none --init --shm-size=1g \
    -e PUID="$(id -u)" -e PGID="$(id -g)" \
    -v "$work:/workspace" -v "$root/tests/fixtures/playwright:/proof:ro" \
    "$image" node /proof/check.cjs | tee "$root/out/playwright/acceptance.json"
  test -s "$work/chromium.png" && test -s "$work/firefox.png" && test -s "$work/webkit.png"
  bash "$root/tests/fixtures/playwright/parity.sh" "$image" "$line"
  exit 0
fi
kind=${family%-dev}
case "$family" in php-browser|php-toolkit|php-serena|php-frankenphp|uxor-dev) kind=php ;; esac
work=$(mktemp -d)
project="image-check-${RANDOM}-${RANDOM}"
cp -a "$root/tests/fixtures/$kind/." "$work/"
cp "$root/tests/fixtures/native-check.c" "$work/"
if [[ "$family" = php-frankenphp || "$family" = uxor-dev ]]; then
  cp "$root/tests/fixtures/frankenphp/Caddyfile" "$work/"
  cp "$root/tests/fixtures/frankenphp/index.php" "$work/public/index.php"
fi
export IMAGE="$image" WORKSPACE="$work" PUID PGID
PUID=$(id -u); PGID=$(id -g)
compose=(docker compose -p "$project" -f "$root/examples/php/compose.yaml")
overrides=
if [[ -n "${CA_CERTIFICATE:-}" ]]; then
  # A conditional override avoids an empty/default bind mount when no CA is
  # supplied. JSON also preserves spaces and Compose punctuation in host paths.
  # Compose rereads it on every call, so keep it outside the writable workspace.
  overrides=$(mktemp -d)
  python3 - "$CA_CERTIFICATE" "$overrides/ca.compose.json" <<'PY'
import json, sys
from pathlib import Path
override = {"services": {"dev": {
    "environment": {"LIBRARY_CA_FILE": "/run/library-proxy.pem"},
    "volumes": [{"type": "bind", "source": sys.argv[1].replace("$", "$$"), "target": "/run/library-proxy.pem",
                 "read_only": True, "bind": {"create_host_path": False}}],
}}}
Path(sys.argv[2]).write_text(json.dumps(override))
PY
  compose+=(-f "$overrides/ca.compose.json")
fi
cleanup() { "${compose[@]}" down --volumes --remove-orphans >/dev/null 2>&1 || true; docker volume rm "$project-cache" >/dev/null 2>&1 || true; rm -rf "$work" ${overrides:+"$overrides"}; }
trap cleanup EXIT
start=$SECONDS
if [[ "$kind" = php || "$kind" = python ]]; then
  "${compose[@]}" run --rm dev bash run.sh
  if [[ "$kind" = php ]]; then
    cp -a "$root/tests/fixtures/mutation" "$work/mutation"
    "${compose[@]}" run --rm -w /workspace/mutation dev bash run.sh
    "${compose[@]}" run --rm dev library-php-coverage xdebug coverage.php xdebug
    "${compose[@]}" run --rm dev library-php-coverage pcov coverage.php pcov
    "${compose[@]}" run --rm -e PHPSTAN_PROJECT=/opt/xorder/php-tools dev \
      library-php-tests phpstan --level=max /workspace/coverage-subject.php
    # Per-process PCOV activation must not rewrite the next app process's ini.
    "${compose[@]}" run --rm dev php -r 'if (!extension_loaded("xdebug") || ini_get("pcov.enabled")) {exit(1);}'
  fi
  test "$(stat -c %u "$work/workspace-proof.txt")" = "$PUID"
  # Cache persists between invocations, independently of service process lifetime.
  # A root host runs with PUID=0, where HOME is /root but the image's cache path
  # still points into the /home/dev cache volume, so check that path.
  "${compose[@]}" run --rm dev bash -c 'cache=${XDG_CACHE_HOME:-$HOME/.cache}; test -d "$cache" && touch "$cache/reuse-proof"'
  if [[ "$kind" = php ]]; then
    "${compose[@]}" run --rm dev bash -c 'cache=${XDG_CACHE_HOME:-$HOME/.cache}; test -f "$cache/cache-proof" && test -f "$cache/reuse-proof"'
  fi
else
  WORKSPACE="$work" CACHE_VOLUME="$project-cache" bash "$root/scripts/run-image.sh" "$image" bash run.sh
  test "$(stat -c %u "$work/workspace-proof.txt")" = "$PUID"
fi
WORKSPACE="$work" CACHE_VOLUME="$project-cache" bash "$root/scripts/run-image.sh" "$image" bash -c 'cc native-check.c -o native-proof && ./native-proof'
bash "$root/tests/fixtures/trust/run.sh" "$image"
if [[ "$family" = uxor-dev ]]; then
  bash "$root/tests/fixtures/uxor/run.sh" "$image"
fi
if [[ "$family" = php-toolkit ]]; then
  IMAGE="$image" TOOLKIT_LOCAL_IMAGE=1 TOOLKIT_REQUIRE_PREPARED=1 bash "$root/tests/fixtures/php-toolkit/run.sh"
fi
if [[ "$family" = php-serena ]]; then
  python3 "$root/tests/fixtures/serena/check.py" "$image"
fi
printf 'Behavioral recipe completed in %ss for %s\n' "$((SECONDS-start))" "$line"

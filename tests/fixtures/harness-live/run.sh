#!/usr/bin/env bash
# Initialize real pinned vendor CLIs, then test them in a network-disabled container.
set -euo pipefail
image=${1:?Supply the harness-live image}
root=$(cd "$(dirname "$0")/../../.." && pwd)
work=$(mktemp -d)
volume="xorder-harness-check-${RANDOM}-${RANDOM}"
cleanup() { docker volume rm "$volume" >/dev/null 2>&1 || true; rm -rf "$work"; }
trap cleanup EXIT
readarray -t consumer < <(python3 - "$root/tests/fixtures/harness-live/consumer.json" <<'PY'
import json, sys
lock = json.load(open(sys.argv[1]))
print(lock['repository'])
print(lock['commit'])
PY
)
git_options=()
trust=()
if [[ -n "${CA_CERTIFICATE:-}" ]]; then
  [[ "$CA_CERTIFICATE" = /* && -f "$CA_CERTIFICATE" && -r "$CA_CERTIFICATE" ]] || { echo 'CA_CERTIFICATE must be a readable absolute PEM file' >&2; exit 64; }
  git_options=(-c "http.sslCAInfo=$CA_CERTIFICATE")
  trust=(--mount "type=bind,src=$CA_CERTIFICATE,dst=/run/library-proxy.pem,readonly" -e LIBRARY_CA_FILE=/run/library-proxy.pem)
fi
git -C "$work" init --quiet
git -C "$work" remote add origin "${consumer[0]}"
GIT_TERMINAL_PROMPT=0 git "${git_options[@]}" -C "$work" -c credential.helper= fetch --quiet --depth=1 origin "${consumer[1]}"
git -C "$work" checkout --quiet --detach FETCH_HEAD
test "$(git -C "$work" rev-parse HEAD)" = "${consumer[1]}"
# mktemp is private to the host user; the read-only consumer must be traversable
# by both tested container UIDs. This fixture checkout contains no credentials.
chmod 0755 "$work"
mkdir -p "$root/out/harness-live"
for uid in 1000 0; do
  # The same private volume is deliberately reused across fresh containers.
  # Initial startup installs once; subsequent startup and readiness run offline.
  docker run --rm --init \
    --mount "type=volume,src=$volume,dst=/home/dev" \
    -e PUID="$uid" -e PGID="$uid" \
    -e HTTP_PROXY -e HTTPS_PROXY -e NO_PROXY \
    "${trust[@]}" \
    "$image" bash -c 'exec harnesses status' > "$root/out/harness-live/online-$uid.json"
  docker run --rm --init --network=none \
    --mount "type=volume,src=$volume,dst=/home/dev" \
    --mount "type=bind,src=$work,dst=/consumer,readonly" \
    --mount "type=bind,src=$root/tests/fixtures/harness-live,dst=/proof,readonly" \
    -e PUID="$uid" -e PGID="$uid" \
    "$image" python3 /proof/check.py > "$root/out/harness-live/acceptance-$uid.json"
done
printf 'Pinned harness installation, offline capabilities, credential-free HOME reuse and real tmux passed\n'

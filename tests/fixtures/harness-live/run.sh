#!/usr/bin/env bash
# Initialize real pinned vendor CLIs, then test them in a network-disabled container.
set -euo pipefail
image=${1:?Supply the harness-live image}
root=$(cd "$(dirname "$0")/../../.." && pwd)
work=$(mktemp -d)
# This empty disposable workspace is shared only by the two fixture UIDs; no
# project or credential bytes enter it. HOME retains its private per-UID volume.
chmod 0777 "$work"
volume_prefix="xorder-harness-check-${RANDOM}-${RANDOM}"
cleanup() { docker volume rm "$volume_prefix-1000" "$volume_prefix-0" >/dev/null 2>&1 || true; rm -rf "$work"; }
trap cleanup EXIT
trust=()
if [[ -n "${CA_CERTIFICATE:-}" ]]; then
  [[ "$CA_CERTIFICATE" = /* && -f "$CA_CERTIFICATE" && -r "$CA_CERTIFICATE" ]] || { echo 'CA_CERTIFICATE must be a readable absolute PEM file' >&2; exit 64; }
  trust=(--mount "type=bind,src=$CA_CERTIFICATE,dst=/run/library-proxy.pem,readonly" -e LIBRARY_CA_FILE=/run/library-proxy.pem)
fi
mkdir -p "$root/out/harness-live"
for uid in 1000 0; do
  # Each UID owns its private HOME; replacement containers reuse only that UID.
  volume="$volume_prefix-$uid"
  python3 "$root/scripts/container_network.py" docker run --rm --init \
    --mount "type=volume,src=$volume,dst=/home/dev" \
    -e PUID="$uid" -e PGID="$uid" \
    "${trust[@]}" \
    "$image" bash -c 'exec harnesses status' > "$root/out/harness-live/online-$uid.json"
  docker run --rm --init --network=none \
    --mount "type=volume,src=$volume,dst=/home/dev" \
    --mount "type=bind,src=$work,dst=/workspace" \
    --mount "type=bind,src=$root/tests/fixtures/harness-live,dst=/proof,readonly" \
    --mount "type=bind,src=$root/tests/fixtures/native-runtime,dst=/runtime,readonly" \
    -e PUID="$uid" -e PGID="$uid" \
    "$image" python3 /proof/check.py > "$root/out/harness-live/acceptance-$uid.json"
  if [[ "$uid" = 1000 ]]; then
    # A prior session can forge its executable and co-located receipt. Root must
    # reject that entire HOME before chown or any managed executable can run.
    for action in tamper snapshot; do
      if [[ "$action" = snapshot ]]; then
        if docker run --rm --init --network=none \
          --mount "type=volume,src=$volume,dst=/home/dev" \
          -e PUID=0 -e PGID=0 -e HARNESS_AUTO_INSTALL=0 \
          "$image" codex --version > "$root/out/harness-live/rejected-root.stdout" \
          2> "$root/out/harness-live/rejected-root.stderr"; then
          echo 'Root reused a lower-UID HOME' >&2; exit 1
        else
          test "$?" = 64
        fi
      fi
      # Bypass startup ownership changes so the after-snapshot cannot repair
      # evidence of an unsafe root chown before inspecting it.
      docker run --rm --network=none --user 1000:1000 --entrypoint python3 \
        --mount "type=volume,src=$volume,dst=/home/dev" \
        --mount "type=bind,src=$root/tests/fixtures/harness-live,dst=/proof,readonly" \
        "$image" /proof/cross_uid.py "$action" > "$root/out/harness-live/cross-uid-$action.json"
    done
    cmp "$root/out/harness-live/cross-uid-tamper.json" "$root/out/harness-live/cross-uid-snapshot.json"
  fi
done
# Exercise actual ownership changes as container root; restricted host UID
# namespaces may be unable to represent UID 1000 in these filesystem tests.
docker run --rm --init --network=none -e PUID=0 -e PGID=0 -e HARNESS_AUTO_INSTALL=0 \
  --mount "type=bind,src=$root,dst=/source,readonly" \
  "$image" python3 -I /source/tests/test_harness_root_trust.py \
  2>&1 | tee "$root/out/harness-live/root-trust-tests.log"
printf 'Verified harness installation, per-UID offline reuse, rejected root promotion and real tmux passed\n'

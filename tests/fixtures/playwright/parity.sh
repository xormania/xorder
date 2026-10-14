#!/usr/bin/env bash
# Compare the candidate with committed consumer baselines; never generate new ones.
set -euo pipefail
browser=${1:?Supply browser image}
line=${2:?Supply browser line}
root=$(cd "$(dirname "$0")/../../.." && pwd)
resolver=(python3 "$root/scripts/playwright_fixture.py" "$root/tests/fixtures/playwright/consumers/${line#*/}.json" "$root/catalog-v2.json")
application_kind=accepted-publication
if [[ -n "${XORDER_PARITY_LOCAL_APPLICATION:-}" ]]; then
  resolver+=(--local-application "$XORDER_PARITY_LOCAL_APPLICATION")
  application_kind=local-source-validation
fi
inputs=$("${resolver[@]}")
mapfile -t consumer <<< "$inputs"
work=$(mktemp -d)
export BROWSER_IMAGE="$browser" WORKSPACE="$work/repo" UXOR_PROJECT="browser-parity-${RANDOM}-${RANDOM}"
export HTTP_PORT=18085 HTTPS_PORT=18445 HTTP3_PORT=18445
export IMAGE="${consumer[3]}"
evidence="$root/out/playwright/${line//\//-}"
mkdir -p "$evidence" "$work/home" "$work/docker"
source_validation_env=()
parity_runner() {
  env -i PATH="$PATH" HOME="$work/home" DOCKER_CONFIG="$work/docker" \
    WORKSPACE="$WORKSPACE" IMAGE="$IMAGE" BROWSER_IMAGE="$BROWSER_IMAGE" \
    UXOR_PROJECT="$UXOR_PROJECT" HTTP_PORT="$HTTP_PORT" HTTPS_PORT="$HTTPS_PORT" HTTP3_PORT="$HTTP3_PORT" \
    XORDER_PARITY_FIXTURE=1 XORDER_SHARED_CACHE=0 \
    "${source_validation_env[@]}" \
    bash "$root/examples/uxor/run.sh" "$@"
}
cleanup() {
  result=$?
  if [ "$result" != 0 ]; then
    parity_runner logs --tail 100 > "$evidence/stack.log" 2>&1 || true
  fi
  for directory in playwright-results playwright-report test-results; do
    if [ -d "$WORKSPACE/$directory" ]; then cp -a "$WORKSPACE/$directory" "$evidence/"; fi
  done
  parity_runner down --volumes --remove-orphans >/dev/null 2>&1 || true
  rm -rf "$work"
}
trap cleanup EXIT
git init "$WORKSPACE"
git -C "$WORKSPACE" remote add origin "${consumer[0]}"
git -C "$WORKSPACE" fetch --depth 1 origin "${consumer[1]}"
git -C "$WORKSPACE" checkout --detach FETCH_HEAD
python3 - "$WORKSPACE" "${consumer[2]}" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
package = json.loads((root / 'package.json').read_text())
lock = json.loads((root / 'package-lock.json').read_text())
assert package['devDependencies']['@playwright/test'] == sys.argv[2]
assert lock['packages']['node_modules/@playwright/test']['version'] == sys.argv[2]
PY
if [[ "$application_kind" == accepted-publication ]]; then docker pull "$IMAGE"; fi
if [[ -n "${XORDER_SOURCE_VALIDATION_PROOF:-}" ]]; then
  # The anonymous verifier's trusted builder owns the candidate allowlist.
  # Consumer code never writes this proof, and env -i forwards only the
  # completed proof path after the pinned companion is observed.
  python3 - "$root" "$XORDER_SOURCE_VALIDATION_PROOF" "$IMAGE" "$BROWSER_IMAGE" "$work/source-validation.json" <<'PY'
import sys
from pathlib import Path
root = Path(sys.argv[1])
sys.path.insert(0, str(root / "scripts"))
from xorder.downstream import prepare_fixture_proof
prepare_fixture_proof(sys.argv[2], {"php": sys.argv[3], "browser": sys.argv[4]}, sys.argv[5], root=root)
PY
  source_validation_env=("XORDER_SOURCE_VALIDATION_PROOF=$work/source-validation.json")
fi
parity_runner up
parity_runner sync
parity_runner exec env CI=1 npx playwright test \
  --project=examples --retries=0 --workers=4 --update-snapshots=none
# Enforce preservation of every committed baseline even if the consumer changes defaults.
git -C "$WORKSPACE" diff --exit-code -- '*.png'
python3 - "$evidence/consumer.json" "${consumer[1]}" "$browser" "$IMAGE" "${consumer[2]}" "$application_kind" <<'PY'
import json, pathlib, sys
pathlib.Path(sys.argv[1]).write_text(json.dumps({'consumer_commit': sys.argv[2], 'browser': sys.argv[3],
    'application_image': sys.argv[4], 'playwright_version': sys.argv[5], 'application_kind': sys.argv[6],
    'project': 'examples', 'baseline_updates': False, 'status': 'passed'}, indent=2) + '\n')
PY

#!/usr/bin/env bash
set -euo pipefail
image=${1:?Supply uxor-dev image}
root=$(cd "$(dirname "$0")/../../.." && pwd)
docker run --rm --mount "type=bind,src=$root,dst=/xorder,readonly" "$image" \
  bash /xorder/tests/fixtures/uxor/verify-composer-reuse.sh
python3 "$root/tests/fixtures/network/check.py" "$image"
work=$(mktemp -d)
export XDG_CACHE_HOME="$work/runner-cache"
export IMAGE="$image" WORKSPACE="$work/repo" UXOR_PROJECT="uxor-check-${RANDOM}-${RANDOM}"
export HTTP_PORT=18084 HTTPS_PORT=18444 HTTP3_PORT=18444
export WORKTREE_GIT=1
# Exercise the profile's default, rather than inheriting a fixture-runner override.
unset BROWSER_MEMORY
seed_workspace="$work/seed-consumer"
seed_project="$UXOR_PROJECT-seed"
cache_workspace="$work/cache-consumer"
cache_project="$UXOR_PROJECT-cache"
cache_run() {
  WORKSPACE="$cache_workspace" UXOR_PROJECT="$cache_project" \
    HTTP_PORT=18086 HTTPS_PORT=18446 HTTP3_PORT=18446 \
    bash "$root/examples/uxor/run.sh" "$@"
}
seed_run() {
  WORKSPACE="$seed_workspace" UXOR_PROJECT="$seed_project" \
    HTTP_PORT=18085 HTTPS_PORT=18445 HTTP3_PORT=18445 \
    bash "$root/examples/uxor/run.sh" "$@"
}
cleanup() {
  status=$?
  trap - EXIT
  if python3 "$root/tests/fixtures/uxor/browser_acceptance.py" archive "$WORKSPACE" \
      "$XDG_CACHE_HOME/xorder/test-attempts" "$work" "$root/out/uxor-runtime/$UXOR_PROJECT"; then
    :
  else
    archive_status=$?
    printf 'Runtime evidence archival failed with exit %s (fixture exit %s)\n' "$archive_status" "$status" >&2
    if [ "$status" = 0 ]; then status=$archive_status; fi
  fi
  if [ -s "$work/oom-container" ]; then
    docker rm --force "$(cat "$work/oom-container")" >/dev/null 2>&1 || true
  fi
  if [ "$status" != 0 ]; then
    bash "$root/examples/uxor/run.sh" logs --tail 100 >/dev/stderr 2>&1 || true
  fi
  if [ -d "$cache_workspace" ]; then
    cache_run down --volumes --remove-orphans >/dev/null 2>&1 || true
  fi
  if [ -d "$seed_workspace" ]; then
    seed_run down --volumes --remove-orphans >/dev/null 2>&1 || true
  fi
  bash "$root/examples/uxor/run.sh" down --volumes --remove-orphans >/dev/null 2>&1 || true
  # Only this disposable cloned fixture, even if a failing command wrote as root.
  if [ -d "$WORKSPACE" ]; then
    docker run --rm -e PUID=0 -e PGID=0 --mount "type=bind,src=$WORKSPACE,dst=/workspace" \
      "$image" find /workspace -mindepth 1 -delete >/dev/null 2>&1 || true
  fi
  rm -rf "$work"
  exit "$status"
}
trap cleanup EXIT
mapfile -t consumer < <(python3 -c 'import json,sys; c=json.load(open(sys.argv[1])); print(c["repository"]); print(c["commit"]); print("\n".join(c["tests"]))' "$root/tests/fixtures/uxor/consumer.json")
git init "$work/main"
git -C "$work/main" remote add origin "${consumer[0]}"
git -C "$work/main" fetch --depth 1 origin "${consumer[1]}"
git -C "$work/main" worktree add --detach "$WORKSPACE" FETCH_HEAD
if [[ -n "${XORDER_SOURCE_VALIDATION_PROOF:-}" ]]; then
  # A trusted builder supplied the exact candidate ID. Resolve the companion
  # from xorder's catalog and the pinned consumer lock before application hooks,
  # then keep the completed proof outside every mounted consumer worktree.
  BROWSER_IMAGE=$(python3 - "$root" "$WORKSPACE" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]) / "examples/uxor"))
from runner import browser_image, playwright
print(browser_image(playwright(Path(sys.argv[2]))))
PY
)
  export BROWSER_IMAGE
  if ! docker image inspect -- "$BROWSER_IMAGE" >/dev/null 2>&1; then docker pull "$BROWSER_IMAGE"; fi
  python3 - "$root" "$XORDER_SOURCE_VALIDATION_PROOF" "$image" "$BROWSER_IMAGE" "$work/source-validation.json" <<'PY'
import sys
from pathlib import Path
root = Path(sys.argv[1])
sys.path.insert(0, str(root / "scripts"))
from xorder.downstream import prepare_fixture_proof
prepare_fixture_proof(sys.argv[2], {"php": sys.argv[3], "browser": sys.argv[4]}, sys.argv[5], root=root)
PY
  export XORDER_SOURCE_VALIDATION_PROOF="$work/source-validation.json"
fi
bash "$root/examples/uxor/run.sh" up
bash "$root/examples/uxor/run.sh" sync
bash "$root/examples/uxor/run.sh" sync --check
bash "$root/examples/uxor/run.sh" status
bash "$root/examples/uxor/run.sh" exec test -s demo/var/tailwind/app.built.css
before_setup=$(bash "$root/examples/uxor/run.sh" exec bash -c 'cat demo/var/xorder/composer-ready demo/var/xorder/node-ready')
bash "$root/examples/uxor/run.sh" up
bash "$root/examples/uxor/run.sh" status
# Matching setup avoids package reinstalls; the recorded content stays stable.
after_setup=$(bash "$root/examples/uxor/run.sh" exec bash -c 'cat demo/var/xorder/composer-ready demo/var/xorder/node-ready')
test "$before_setup" = "$after_setup"
# Complete dependencies can be adopted with unrecorded worktree setup, without
# inventing receipts or allowing writes through the mounted dependency paths.
bash "$root/examples/uxor/run.sh" exec rm demo/var/xorder/composer-ready demo/var/xorder/node-ready
bash "$root/examples/uxor/run.sh" up --reuse-only > "$work/reuse-only.log" 2>&1 || { cat "$work/reuse-only.log"; exit 1; }
grep -q 'readiness marker is missing' "$work/reuse-only.log"
bash "$root/examples/uxor/run.sh" exec test ! -e demo/var/xorder/composer-ready
bash "$root/examples/uxor/run.sh" exec test ! -e demo/var/xorder/node-ready
for directory in demo/vendor node_modules demo/assets/vendor; do
  if bash "$root/examples/uxor/run.sh" exec touch "$directory/.xorder-write-probe"; then
    echo "Reuse-only dependency directory was writable: $directory" >&2
    exit 1
  fi
done
# Ordinary setup remains available when deliberately returning to private,
# writable dependency mounts. It records its own hooks and npm installation.
bash "$root/examples/uxor/run.sh" up
# Restore an accidentally omitted manifest from captured Symfony metadata.
asset_metadata=$(bash "$root/examples/uxor/run.sh" exec sha256sum demo/assets/vendor/installed.php)
bash "$root/examples/uxor/run.sh" exec rm demo/assets/vendor/installed.php
bash "$root/examples/uxor/run.sh" up > "$work/asset-reuse.log" 2>&1 || { cat "$work/asset-reuse.log"; exit 1; }
grep -q 'Restored Symfony importmap metadata' "$work/asset-reuse.log"
test "$asset_metadata" = "$(bash "$root/examples/uxor/run.sh" exec sha256sum demo/assets/vendor/installed.php)"
docker run --rm --network none \
  --mount "type=bind,src=$root,dst=/xorder,readonly" \
  --mount "type=bind,src=$WORKSPACE,dst=/app,readonly" \
  "$image" php /xorder/tests/fixtures/uxor/verify-importmap-reuse.php /app/demo/vendor/autoload.php

test "$(bash "$root/examples/uxor/run.sh" exec git rev-parse HEAD)" = "${consumer[1]}"
# The public cache command must import into a true cold checkout without a
# running PHP service, and ordinary up must use those authenticated snapshots.
bash "$root/examples/uxor/run.sh" cache export --output /app/dependencies.zip
bundle_sha256=$(sha256sum "$WORKSPACE/dependencies.zip" | cut -d ' ' -f 1)
bash "$root/examples/uxor/run.sh" down
git -C "$work/main" worktree add --detach "$cache_workspace" FETCH_HEAD
cp "$WORKSPACE/dependencies.zip" "$cache_workspace/dependencies.zip"
test ! -d "$cache_workspace/demo/vendor"
test ! -d "$cache_workspace/demo/assets/vendor"
cache_run cache import --input /app/dependencies.zip --sha256 "$bundle_sha256"
cache_run up > "$work/cold-import-up.log" 2>&1 || { cat "$work/cold-import-up.log"; exit 1; }
# Composer hooks/readiness remain real; a vendor reinstall would defeat reuse.
! grep -q 'Installing dependencies from lock file' "$work/cold-import-up.log"
cache_run exec bash -euc 'cd demo; php /run/xorder/verify-composer.php verify; php /run/xorder/importmap-state.php verify'
cache_run exec test -s demo/var/tailwind/app.built.css
cache_run down --volumes
rm -f "$WORKSPACE/dependencies.zip" "$cache_workspace/dependencies.zip"
# A clean receiver shares only dependency files. Its own synced recipe copies,
# Symfony runtime output and Compose volumes must remain private.
bash "$root/examples/uxor/run.sh" down
git -C "$work/main" worktree add --detach "$seed_workspace" FETCH_HEAD
test ! -e "$seed_workspace/demo/templates/layouts/base.html.twig"
seed_run seed --from "$WORKSPACE" --hardlink
XORDER_REUSE_ONLY=0 seed_run up
for file in demo/vendor/autoload.php node_modules/.package-lock.json demo/assets/vendor/installed.php; do
  test "$(stat -c '%d:%i' "$WORKSPACE/$file")" = "$(stat -c '%d:%i' "$seed_workspace/$file")"
  if seed_run exec touch "$file"; then
    echo "Seeded receiver dependency was writable: $file" >&2
    exit 1
  fi
done
recipe_copy=demo/templates/layouts/base.html.twig
cmp "$seed_workspace/layouts/templates/layouts/base.html.twig" "$seed_workspace/$recipe_copy"
test "$(stat -c '%d:%i' "$WORKSPACE/$recipe_copy")" != "$(stat -c '%d:%i' "$seed_workspace/$recipe_copy")"
seed_run exec test -s demo/var/tailwind/app.built.css
seed_run down --volumes
# Both ends of the share are guarded, including an ordinary donor up with an
# explicit reuse opt-out. No second install or browser test run is needed.
XORDER_REUSE_ONLY=0 bash "$root/examples/uxor/run.sh" up
for file in demo/vendor/autoload.php node_modules/.package-lock.json demo/assets/vendor/installed.php; do
  if bash "$root/examples/uxor/run.sh" exec touch "$file"; then
    echo "Seed donor dependency was writable: $file" >&2
    exit 1
  fi
done
bash "$root/examples/uxor/run.sh" exec git status --porcelain
bash "$root/examples/uxor/run.sh" exec bash -c 'cd demo && composer check-platform-reqs'
bash "$root/examples/uxor/run.sh" exec bash -c \
  'cd demo && cmp /opt/tailwind/tailwindcss-linux-x64 "var/tailwind/$(cat /opt/tailwind/version)/tailwindcss-linux-x64" && php bin/console tailwind:build'
bash "$root/examples/uxor/run.sh" php-tests all
bash "$root/examples/uxor/run.sh" exec php -r \
  '$report=simplexml_load_file("demo/var/phpunit-coverage.xml"); if (!$report || (int)$report->project->metrics["coveredstatements"] < 1) { throw new RuntimeException("PHPUnit must record executed statements"); }'
# A source plant survives a second sync immediately before a real spec fetches
# the page, fails that spec, and restores the ignored generated copy afterward.
python3 - "$WORKSPACE" <<'PY'
import json
from pathlib import Path
import sys
workspace = Path(sys.argv[1])
(workspace / ".xorder").mkdir(exist_ok=True)
contract = {"schema_version": 1, "plants": {"fixture-markup": {
    "edits": [{"path": "layouts/templates/layouts/base.html.twig",
               "search": "<!DOCTYPE html>",
               "replace": "<!DOCTYPE html>\n<!-- xorder-fixture-plant -->"}],
    "confirm": {"command": ["curl", "--fail", "--silent", "--show-error", "--insecure",
                             "--noproxy", "*", "--max-time", "15", "https://localhost/demo/blank"],
                "contains": "xorder-fixture-plant"}}}}
(workspace / ".xorder/testing.json").write_text(json.dumps(contract))
(workspace / "tests/e2e/xorder.plant.spec.ts").write_text("""import { test, expect } from '@playwright/test';
import { execFileSync } from 'node:child_process';
test('source plant survives pre-test recipe sync', async ({ request }) => {
  execFileSync('php', ['tools/sync-demo'], { cwd: process.cwd(), stdio: 'ignore' });
  const response = await request.get('/demo/blank');
  expect(response.ok()).toBeTruthy();
  expect(await response.text()).not.toContain('xorder-fixture-plant');
});
""")
PY
if bash "$root/examples/uxor/run.sh" plant fixture-markup -- tests/e2e/xorder.plant.spec.ts --workers=1; then
  echo 'The served source plant unexpectedly passed its detection spec' >&2
  exit 1
else
  test "$?" = 1
fi
git -C "$WORKSPACE" diff --exit-code -- layouts/templates/layouts/base.html.twig
bash "$root/examples/uxor/run.sh" sync --check
! grep -q xorder-fixture-plant "$WORKSPACE/demo/templates/layouts/base.html.twig"
rm "$WORKSPACE/.xorder/testing.json" "$WORKSPACE/tests/e2e/xorder.plant.spec.ts"
# The pinned consumer has only Chromium projects. Exercise its existing 45
# snapshot-free behavioral cases with all three actual browserName overrides;
# shared upstream Chromium screenshot baselines are deliberately left alone.
python3 "$root/tests/fixtures/uxor/browser_acceptance.py" baseline "$UXOR_PROJECT" "$work/browser-baseline.json"
# Both PHP variants use the same browser image. Keep the wider workload and
# isolated OOM proof on 8.5; 8.4 retains its existing 45 Chromium behavior cases.
cross_browser=$(bash "$root/examples/uxor/run.sh" exec php -r 'echo PHP_MAJOR_VERSION === 8 && PHP_MINOR_VERSION === 5 ? "1" : "0";')
normal_status=0
if [ "$cross_browser" = 1 ]; then
  python3 "$root/tests/fixtures/uxor/browser_acceptance.py" config "$WORKSPACE"
  bash "$root/examples/uxor/run.sh" test --attest-server --config=xorder.cross-browser.config.ts \
    --workers=2 --retries=0 --timeout=30000 --global-timeout=300000 "${consumer[@]:2}" || normal_status=$?
else
  bash "$root/examples/uxor/run.sh" test --attest-server "${consumer[@]:2}" || normal_status=$?
fi
# Observe the normal stack and probe an isolated child OOM even if a consumer
# assertion failed. Keep the original behavior exit when another check also fails.
memory_status=0
python3 "$root/tests/fixtures/uxor/browser_acceptance.py" normal "$UXOR_PROJECT" \
  "$work/browser-baseline.json" 2>&1 | tee "$work/normal-memory.log" || memory_status=$?
oom_status=0
if [ "$cross_browser" = 1 ]; then
  python3 "$root/tests/fixtures/uxor/browser_acceptance.py" oom "$UXOR_PROJECT" \
    "$work/browser-baseline.json" "$work/oom-container" 2>&1 | tee "$work/child-oom.log" || oom_status=$?
fi
printf 'behavior=%s normal_memory=%s isolated_child_oom=%s\n' \
  "$normal_status" "$memory_status" "$oom_status" | tee "$work/workload-status.log"
if [ "$normal_status" != 0 ]; then exit "$normal_status"; fi
if [ "$memory_status" != 0 ]; then exit "$memory_status"; fi
if [ "$oom_status" != 0 ]; then exit "$oom_status"; fi
# Audit the actual pinned consumer run rather than reconstructing cases from
# the requested filenames or treating baseURL configuration as server evidence.
python3 - "$XDG_CACHE_HOME/xorder/test-attempts" "$root/tests/fixtures/uxor/browser_acceptance.py" "$cross_browser" <<'PY'
import importlib.util
import json
from pathlib import Path
import sys
receipts = [json.loads(path.read_text()) for path in Path(sys.argv[1]).glob("*/receipt.json")]
plants = [receipt for receipt in receipts if receipt["plant_name"] == "fixture-markup"]
assert len(plants) == 1 and plants[0]["exit_code"] == 1, plants
assert any(case["status"] == "failed" for case in plants[0]["observed_test_attempts"])
normal = [receipt for receipt in receipts if receipt["plant_name"] is None]
assert len(normal) == 1, normal
receipt = normal[0]
assert receipt["exit_code"] == 0, receipt
assert receipt["observer_status"] == "complete", receipt["observation_errors"]
assert any(case["status"] == "passed" for case in receipt["observed_test_attempts"])
assert receipt["container_demo_url"] == "https://localhost"
navigation = receipt["actual_navigation_urls"]
assert navigation["status"] == "observed", navigation
urls = [url for attempt in navigation["attempts"]
        for key in ("request_urls", "frame_urls") for url in attempt[key]]
assert any(url.startswith("https://localhost/") for url in urls), urls
assert len(receipt["host_start"]["loadavg"]) == 3
assert receipt["started_at"] <= receipt["ended_at"]
spec = importlib.util.spec_from_file_location("browser_acceptance", sys.argv[2])
acceptance = importlib.util.module_from_spec(spec)
spec.loader.exec_module(acceptance)
if sys.argv[3] == "1":
    acceptance.verify_behavior(receipt)
else:
    assert receipt["selected_test_count"] == 45 and len(receipt["observed_test_attempts"]) == 45
PY
# Composer, Node and the app must write the host mount as the requested user.
test "$(stat -c %u "$WORKSPACE/node_modules")" = "$(id -u)"
test "$(stat -c %u "$WORKSPACE/demo/vendor")" = "$(id -u)"

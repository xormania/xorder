#!/usr/bin/env bash
set -euo pipefail
image=${1:?Supply flowbite-xor-dev image}
root=$(cd "$(dirname "$0")/../../.." && pwd)
docker run --rm --mount "type=bind,src=$root,dst=/xorder,readonly" "$image" \
  bash /xorder/tests/fixtures/flowbite-xor/verify-composer-reuse.sh
python3 "$root/tests/fixtures/network/check.py" "$image"
work=$(mktemp -d)
export XDG_CACHE_HOME="$work/runner-cache"
export IMAGE="$image" WORKSPACE="$work/repo" FLOWBITE_PROJECT="flowbite-check-${RANDOM}-${RANDOM}"
export HTTP_PORT=18084 HTTPS_PORT=18444 HTTP3_PORT=18444
export WORKTREE_GIT=1
seed_workspace="$work/seed-consumer"
seed_project="$FLOWBITE_PROJECT-seed"
seed_run() {
  WORKSPACE="$seed_workspace" FLOWBITE_PROJECT="$seed_project" \
    HTTP_PORT=18085 HTTPS_PORT=18445 HTTP3_PORT=18445 \
    bash "$root/examples/uxor/run.sh" "$@"
}
cleanup() {
  status=$?
  if [ "$status" != 0 ]; then
    bash "$root/examples/uxor/run.sh" logs --tail 100 >/dev/stderr 2>&1 || true
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
}
trap cleanup EXIT
mapfile -t consumer < <(python3 -c 'import json,sys; c=json.load(open(sys.argv[1])); print(c["repository"]); print(c["commit"]); print("\n".join(c["tests"]))' "$root/tests/fixtures/flowbite-xor/consumer.json")
git init "$work/main"
git -C "$work/main" remote add origin "${consumer[0]}"
git -C "$work/main" fetch --depth 1 origin "${consumer[1]}"
git -C "$work/main" worktree add --detach "$WORKSPACE" FETCH_HEAD
# The upstream test observes history before Turbo's promoted visit completes.
# Keep this verification-only overlay tied to its reviewed source; changing the
# consumer pin requires removing or reviewing the overlay, not applying it blindly.
if [[ "${consumer[1]}" != c8878af66897d8c10af694050a7a588166942117 ]]; then
  printf 'Review the frame-navigation completion overlay for the new consumer pin\n' >&2
  exit 1
fi
fixture_patch="$root/tests/fixtures/flowbite-xor/frame-navigation-completion.patch"
printf 'Applying xorder-owned test synchronization overlay to pinned uxor %s\n' "${consumer[1]}"
git -C "$WORKSPACE" apply --check "$fixture_patch"
git -C "$WORKSPACE" apply --whitespace=error "$fixture_patch"
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
  "$image" php /xorder/tests/fixtures/flowbite-xor/verify-importmap-reuse.php /app/demo/vendor/autoload.php

test "$(bash "$root/examples/uxor/run.sh" exec git rev-parse HEAD)" = "${consumer[1]}"
# The same prepared dependency artifacts must work in another clean worktree
# with networking disabled, including Symfony's importmap installation metadata.
bash "$root/examples/uxor/run.sh" cache export --output /app/dependencies.zip
bundle_sha256=$(sha256sum "$WORKSPACE/dependencies.zip" | cut -d ' ' -f 1)
git -C "$work/main" worktree add --detach "$work/cache-consumer" FETCH_HEAD
mkdir -p "$work/imported-cache"
cp "$WORKSPACE/dependencies.zip" "$work/cache-consumer/dependencies.zip"
docker run --rm --network=none \
  -e PUID="$(id -u)" -e PGID="$(id -g)" -e XORDER_CACHE_IMAGE="$image" -e BUNDLE_SHA256="$bundle_sha256" \
  -v "$work/cache-consumer:/app" -v "$work/imported-cache:/run/xorder-cache" \
  -v "$root/examples/flowbite-xor:/profile:ro" -w /app/demo "$image" bash -euc '
    php /app/tools/sync-demo
    python3 /profile/cache.py import --input /app/dependencies.zip --sha256 "$BUNDLE_SHA256"
    php /profile/verify-composer.php verify
    php /profile/importmap-state.php verify
  '
rm -f "$WORKSPACE/dependencies.zip"
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
                             "--noproxy", "*", "--max-time", "15", "https://localhost/"],
                "contains": "xorder-fixture-plant"}}}}
(workspace / ".xorder/testing.json").write_text(json.dumps(contract))
(workspace / "tests/e2e/xorder.plant.spec.ts").write_text("""import { test, expect } from '@playwright/test';
import { execFileSync } from 'node:child_process';
test('source plant survives pre-test recipe sync', async ({ request }) => {
  execFileSync('php', ['tools/sync-demo'], { cwd: process.cwd(), stdio: 'ignore' });
  const response = await request.get('/');
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
bash "$root/examples/uxor/run.sh" test --attest-server "${consumer[@]:2}"
# Audit the actual pinned consumer run rather than reconstructing cases from
# the requested filenames or treating baseURL configuration as server evidence.
python3 - "$XDG_CACHE_HOME/xorder/test-attempts" <<'PY'
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
PY
# Composer, Node and the app must write the host mount as the requested user.
test "$(stat -c %u "$WORKSPACE/node_modules")" = "$(id -u)"
test "$(stat -c %u "$WORKSPACE/demo/vendor")" = "$(id -u)"

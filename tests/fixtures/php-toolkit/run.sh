#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/../../.." && pwd -P)
if [[ -n ${IMAGE:-} ]]; then
  python3 "$root/tests/fixtures/network/check.py" "$IMAGE"
  export TOOLKIT_NETWORK=none
fi
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
mapfile -t consumer < <(python3 - "$root/tests/fixtures/php-toolkit/consumer.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1]))
print(data['repository'])
print(data['commit'])
print(data['recipe'])
print(data['installed_file'])
PY
)
git init -q "$work/consumer"
git -C "$work/consumer" remote add origin "${consumer[0]}"
git -C "$work/consumer" fetch -q --depth 1 origin "${consumer[1]}"
git -C "$work/consumer" checkout -q --detach FETCH_HEAD
test "$(git -C "$work/consumer" rev-parse HEAD)" = "${consumer[1]}"
test ! -e "$work/consumer/demo/vendor"
bash "$root/examples/php-toolkit/run.sh" check "$work/consumer"
echo 'ok: committed uxor kit validates without demo/vendor'

# Exercise the real linter against malformed input, rather than mocking its exit code.
mkdir "$work/broken"
git -C "$work/consumer" archive HEAD | tar -x -C "$work/broken"
printf '{invalid json\n' > "$work/broken/manifest.json"
if KIT_MODE=directory bash "$root/examples/php-toolkit/run.sh" lint "$work/broken" > "$work/broken.log" 2>&1; then
  echo 'Malformed manifest passed the toolkit linter' >&2
  exit 1
fi
grep -q 'Unable to load kit' "$work/broken.log"
cat "$work/broken.log"
echo 'ok: malformed kit input fails validation'

app=$work/first-app
bash "$root/examples/php-toolkit/run.sh" fresh "$app"
test ! -e "$app/${consumer[3]}"
kit=$app/vendor/symfony/ux-toolkit/kits/xorder-consumer
mkdir -p "$kit"
git -C "$work/consumer" archive HEAD | tar -x -C "$kit"
if [[ -n ${IMAGE:-} ]]; then
  docker run --rm --init -e PUID="${PUID:-$(id -u)}" -e PGID="${PGID:-$(id -g)}" \
    --network none \
    --mount "type=bind,src=$app,dst=/workspace" -w /workspace \
    "$IMAGE" php bin/console ux:install "${consumer[2]}" --kit=xorder-consumer --no-interaction
else
  (cd "$app" && "${PHP_BIN:-php}" bin/console ux:install "${consumer[2]}" --kit=xorder-consumer --no-interaction)
fi
test -s "$app/${consumer[3]}"
echo 'ok: ux:install copies the real button recipe into the independent locked app'

second=$work/second-app
bash "$root/examples/php-toolkit/run.sh" fresh "$second"
test ! -e "$second/${consumer[3]}"
test ! -e "$second/vendor/symfony/ux-toolkit/kits/xorder-consumer"
cmp "$root/examples/php-toolkit/symfony-7.4/composer.lock" "$second/composer.lock"
echo 'ok: a second baseline keeps the lock and contains no prior kit or installed recipe'

if bash "$root/examples/php-toolkit/run.sh" fresh "$app" > "$work/existing.log" 2>&1; then
  echo 'Fresh preparation overwrote an existing application' >&2
  exit 1
fi
grep -q 'destination must not exist' "$work/existing.log"
test -s "$app/${consumer[3]}"
echo 'ok: existing application destinations are refused and preserved'

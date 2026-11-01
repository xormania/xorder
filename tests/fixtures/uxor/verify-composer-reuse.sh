#!/usr/bin/env bash
# Real offline Composer installs, with deliberately different source/dist refs.
set -euo pipefail
root=$(cd "$(dirname "$0")/../../.." && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
export COMPOSER_HOME="$work/home" COMPOSER_ALLOW_SUPERUSER=1 COMPOSER_DISABLE_NETWORK=1
mkdir -p "$work/source/src" "$work/project"
printf '%s\n' '<?php namespace XorderFixture; final class Probe {}' > "$work/source/src/Probe.php"
printf '%s\n' '{"name":"xorder/reuse-fixture","autoload":{"psr-4":{"XorderFixture\\":"src/"}}}' > "$work/source/composer.json"
git -C "$work/source" init -q
git -C "$work/source" add .
git -C "$work/source" -c user.name=Fixture -c user.email=fixture@example.test commit -qm fixture
reference=$(git -C "$work/source" rev-parse HEAD)
php -r '$zip=new ZipArchive(); $zip->open($argv[2],ZipArchive::CREATE); foreach (["composer.json","src/Probe.php"] as $file) {$zip->addFile($argv[1]."/".$file,"package/".$file);} $zip->close();' "$work/source" "$work/package.zip"
php -r '$package=["name"=>"xorder/reuse-fixture","version"=>"1.0.0","autoload"=>["psr-4"=>["XorderFixture\\"=>"src/"]],"source"=>["type"=>"git","url"=>$argv[1],"reference"=>$argv[2]],"dist"=>["type"=>"zip","url"=>"file://".$argv[3],"reference"=>"dist-reference"]]; file_put_contents($argv[4],json_encode(["name"=>"xorder/fixture-consumer","require"=>["xorder/reuse-fixture"=>"1.0.0"],"repositories"=>[["type"=>"package","package"=>$package],["packagist.org"=>false]]]));' "$work/source" "$reference" "$work/package.zip" "$work/project/composer.json"
cd "$work/project"
composer update --prefer-dist --no-interaction --no-progress --no-scripts --no-plugins --no-audit
php "$root/examples/uxor/verify-composer.php" verify
php "$root/examples/uxor/verify-composer.php" fingerprint
version=$(composer --version --no-ansi)
policy="$root/examples/uxor/composer-dist.php"
php "$policy" "$version" "$(composer config source-fallback --no-plugins)"
# A project/global fallback opt-in must not be silently accepted.
composer config source-fallback true
if php "$policy" "$version" "$(composer config source-fallback --no-plugins)"; then
  echo 'Enabled source fallback was incorrectly accepted' >&2
  exit 1
fi
composer config source-fallback false
if php "$policy" 'Composer version 2.9.5' false; then
  echo 'Composer without the source-fallback guard was incorrectly accepted' >&2
  exit 1
fi
cp composer.lock "$work/complete.lock"
php -r '$p="composer.lock"; $l=json_decode(file_get_contents($p),true); unset($l["packages"][0]["dist"]); file_put_contents($p,json_encode($l));'
if php "$policy" "$version" false; then
  echo 'A source-only locked package was incorrectly accepted' >&2
  exit 1
fi
cp "$work/complete.lock" composer.lock
# Real failed archive download with a usable local Git source. Track clone
# attempts, not just the final exit code; no network endpoint is required.
rm -rf vendor
mv "$work/package.zip" "$work/package.saved.zip"
mkdir "$work/bin"
XORDER_FIXTURE_REAL_GIT=$(command -v git)
export XORDER_FIXTURE_REAL_GIT XORDER_FIXTURE_GIT_CLONES="$work/clones"
cat > "$work/bin/git" <<'GIT'
#!/usr/bin/env bash
for argument in "$@"; do
  if [[ "$argument" = clone ]]; then printf 'clone\n' >> "$XORDER_FIXTURE_GIT_CLONES"; fi
done
exec "$XORDER_FIXTURE_REAL_GIT" "$@"
GIT
chmod 755 "$work/bin/git"
php "$policy" "$version" false
if PATH="$work/bin:$PATH" COMPOSER_DISABLE_NETWORK=0 composer install --prefer-dist --no-cache --no-interaction --no-progress --no-scripts --no-plugins > "$work/dist-failure.log" 2>&1; then
  cat "$work/dist-failure.log" >&2
  echo 'A missing dist archive did not fail' >&2
  exit 1
fi
if [ -s "$XORDER_FIXTURE_GIT_CLONES" ]; then
  cat "$work/dist-failure.log" >&2
  echo 'A missing dist archive attempted a Git source clone' >&2
  exit 1
fi
# Composer 2.11 removed fallback entirely, including its old diagnostic text.
# Bind the expected failure to our missing archive instead of upstream wording.
if ! grep -Fq "$work/package.zip" "$work/dist-failure.log"; then
  cat "$work/dist-failure.log" >&2
  echo 'The failed install did not report the missing dist archive' >&2
  exit 1
fi
mv "$work/package.saved.zip" "$work/package.zip"
composer install --prefer-dist --no-interaction --no-progress --no-scripts --no-plugins
# Composer labels even local Git transport as network; this sole source is a
# local absolute path, with Packagist disabled and no external repositories.
COMPOSER_DISABLE_NETWORK=0 composer reinstall xorder/reuse-fixture --prefer-source --no-interaction --no-progress --no-scripts --no-plugins
php "$root/examples/uxor/verify-composer.php" verify
if php "$policy" "$version" false; then
  echo 'An in-place update could have retained a source checkout' >&2
  exit 1
fi
# A stale installed record cannot be accepted just because vendor exists.
php -r '$path="vendor/composer/installed.json"; $data=json_decode(file_get_contents($path),true); $data["packages"][0]["version"]="0.0.0"; file_put_contents($path,json_encode($data));'
if php "$root/examples/uxor/verify-composer.php" verify; then
  echo 'A stale vendor package was incorrectly accepted' >&2
  exit 1
fi

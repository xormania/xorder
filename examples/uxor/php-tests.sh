#!/usr/bin/env bash
# Project-owned PHPUnit/configuration plus explicitly selected prepared PHPStan.
set -euo pipefail
task=${1:-all}
if [ "$#" -gt 0 ]; then shift; fi
command -v library-php-tests >/dev/null || {
  echo 'Select a verified uxor image with php-testing and pcov capabilities.' >&2
  exit 69
}
export APP_ENV=test APP_DEBUG=1 CREATE_SNAPSHOTS=false
export PHPUNIT_PROJECT=${PHPUNIT_PROJECT:-/app/demo}
export PHPSTAN_PROJECT=${PHPSTAN_PROJECT:-/opt/xorder/php-tools}
export PHPSTAN_WORKSPACE=${PHPSTAN_WORKSPACE:-/app}
export PHPSTAN_CONFIGURATION=${PHPSTAN_CONFIGURATION:-/app/tools/phpstan.neon}
export PHPSTAN_AUTOLOAD_FILE=${PHPSTAN_AUTOLOAD_FILE:-/app/demo/vendor/autoload.php}
export COVERAGE_SOURCE=${COVERAGE_SOURCE:-/app}
export COVERAGE_CLOVER=${COVERAGE_CLOVER:-/app/demo/var/phpunit-coverage.xml}
if [[ "$task" = phpstan || "$task" = all ]]; then
  (cd "$PHPUNIT_PROJECT" && php bin/console cache:warmup --env=test --no-interaction)
  if [ -z "${PHPSTAN_PATHS:-}" ]; then
    PHPSTAN_PATHS=$(php -r '
      $paths=[];
      foreach (glob("/app/*/manifest.json") as $manifest) {
        $path=dirname($manifest)."/src";
        if (is_dir($path)) {$paths[]=$path;}
      }
      foreach (["/app/demo/src/Demo", "/app/demo/tests"] as $path) {
        if (is_dir($path)) {$paths[]=$path;}
      }
      echo json_encode($paths, JSON_THROW_ON_ERROR);')
    export PHPSTAN_PATHS
  fi
fi
cd "$PHPUNIT_PROJECT"
exec library-php-tests "$task" "$@"

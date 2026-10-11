#!/usr/bin/env bash
set -euo pipefail
profile=$(cd "$(dirname "$0")" && pwd)
if [[ "${1:-}" = --entrypoint ]]; then
  shift
  entry_mode=--application
  if [[ "${1:-}" = --check-reuse ]]; then
    entry_mode=--check-reuse
    shift
  fi
  if [[ "${1:-}" = --seed-sync ]]; then
    entry_mode=--seed-sync
    shift
  fi
  uid=${PUID:-1000}; gid=${PGID:-1000}
  [[ "$uid" =~ ^[0-9]+$ && "$gid" =~ ^[0-9]+$ ]] || exit 64
  if [[ $(id -u) = 0 ]]; then
    # Only the profile-owned cache volume, never the source or host Composer cache.
    chown -R "$uid:$gid" /app/demo/var
  fi
  cd /app/demo
  if [[ -n "${LIBRARY_CA_FILE:-}" ]]; then
    additional_ca=$(mktemp /tmp/xorder-additional-ca.XXXXXXXX.pem)
    python3 "$profile/trust.py" "$LIBRARY_CA_FILE" "$additional_ca"
    chmod 0644 "$additional_ca"
    if [[ -s "$additional_ca" ]]; then
      export LIBRARY_CA_FILE="$additional_ca"
    else
      unset LIBRARY_CA_FILE
      rm -f "$additional_ca"
    fi
  fi
  exec bash /usr/local/bin/library-entrypoint bash "$profile/startup.sh" "$entry_mode" "$@"
fi
mode=${1:?Supply --prepare or --application}; shift
[[ "$mode" = --prepare || "$mode" = --application || "$mode" = --check-reuse || "$mode" = --seed-sync ]] || exit 64
if [[ "$mode" = --seed-sync ]]; then
  [[ "$#" -gt 0 ]] || exit 64
  cd /app/
  exec "$@"
fi
cd /app/demo
reuse=${XORDER_REUSE_ONLY:-0}
[[ "$reuse" = 0 || "$reuse" = 1 ]] || { echo 'XORDER_REUSE_ONLY must be 0 or 1' >&2; exit 64; }
[[ "$mode" != --check-reuse ]] || reuse=1
preference=${COMPOSER_INSTALL_PREFERENCE:-dist}
if [[ "$reuse" = 0 && "$preference" != dist ]]; then
  echo 'up installs from dist only. Remove COMPOSER_INSTALL_PREFERENCE=source; source clones can exhaust the sandbox disk. Use up --reuse-only with complete existing dependencies.' >&2
  exit 64
fi
# A development profile always installs dev requirements and regenerates normal
# autoloads. Do not silently inherit install flags from a production shell.
unset COMPOSER_NO_DEV COMPOSER_NO_SCRIPTS
if [[ $(id -u) = 0 ]]; then
  export COMPOSER_ALLOW_SUPERUSER=1
fi
if [[ "$reuse" = 1 ]]; then
  bash "$profile/reuse.sh"
  [[ "$mode" != --check-reuse ]] || exit 0
else
  php /app/tools/sync-demo
  composer validate --no-check-publish --no-interaction
  mkdir -p var/xorder
  # Both trees include their original installation metadata. Normal project
  # verification and hooks below still decide whether they are usable.
  python3 "$profile/cache.py" restore
  # Restore only a previously recorded, byte-matching Symfony installation.
  php "$profile/importmap-state.php" restore
  marker=var/xorder/composer-ready
  fingerprint() {
    php "$profile/verify-composer.php" fingerprint
  }
  if php "$profile/verify-composer.php" verify; then
    before=$(fingerprint)
    if [[ ! -f "$marker" || $(cat "$marker") != "$before" ]]; then
      composer dump-autoload --no-interaction
      # Imported vendor bytes still need the application's own setup hooks.
      if php "$profile/verify-composer.php" has-hook; then
        composer run-script --no-interaction post-install-cmd
      fi
    else
      echo 'Reusing verified Composer dependencies and setup'
    fi
  else
    composer_version=$(composer --version --no-ansi)
    if ! fallback=$(composer config source-fallback --no-interaction --no-plugins --no-scripts); then
      echo 'Cannot verify Composer source-fallback; use a supported pinned image or up --reuse-only.' >&2
      exit 1
    fi
    php "$profile/composer-dist.php" "$composer_version" "$fallback"
    if ! composer install --prefer-dist --no-progress --no-interaction; then
      echo 'Dist-only installation failed. Prepare dependencies where archive downloads work, then use up --reuse-only; xorder will not retry with source clones.' >&2
      exit 1
    fi
  fi
  php "$profile/verify-composer.php" verify
  # Composer reuse does not prove that importmap assets are still complete.
  if ! php "$profile/importmap-state.php" verify; then
    php bin/console importmap:install --no-interaction
  fi
  php "$profile/importmap-state.php" record
  fingerprint > "$marker.tmp"
  mv "$marker.tmp" "$marker"
  python3 "$profile/cache.py" store
fi
flowbite-prime-tailwind
if [[ "$mode" = --application ]]; then
  # The worker-served page renders Twig's Tailwind asset. Seeding the CLI alone
  # leaves that page at HTTP 500 until the project's CSS has been compiled.
  # Build before launching FrankenPHP; retained healthy services do not restart
  # or rebuild CSS when the host runner only invokes --prepare again.
  php bin/console tailwind:build --no-interaction
  # Keep the project's runtime, database wait and docker-php-entrypoint behavior.
  exec sh /app/demo/frankenphp/docker-entrypoint.sh "$@"
fi

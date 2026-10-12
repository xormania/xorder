#!/usr/bin/env bash
# Inspect existing dependencies; never repair, install, restore or run hooks.
set -uo pipefail
profile=$(cd "$(dirname "$0")" && pwd)
cd /app/demo
failed=0
if ! composer validate --no-check-publish --no-interaction --no-plugins --no-scripts; then
  failed=1
fi
if php "$profile/verify-composer.php" verify; then
  if value=$(php "$profile/verify-composer.php" fingerprint); then
    if [[ ! -f var/xorder/composer-ready || $(cat var/xorder/composer-ready) != "$value" ]]; then
      echo 'Reuse-only: Composer readiness marker is missing or changed; packages verified, setup hooks have not been recorded for these inputs and will not run.' >&2
    fi
  else
    failed=1
  fi
else
  failed=1
fi
if value=$(cd /app && node "$profile/node-state.cjs" inspect); then
  if [[ ! -f var/xorder/node-ready || $(cat var/xorder/node-ready) != "$value" ]]; then
    echo 'Reuse-only: npm readiness marker is missing or changed; installed package metadata verified, npm setup will not run.' >&2
  fi
else
  failed=1
fi
if ! php "$profile/importmap-state.php" verify; then
  failed=1
fi
if [[ "$failed" != 0 ]]; then
  echo 'Reuse-only dependencies are incomplete. Prepare the reported autoload/packages/importmap in a private writable tree, then retry up --reuse-only. Shared dependencies were not repaired.' >&2
  exit 1
fi
echo 'Reuse-only: adopted verified existing dependencies without installation, setup hooks or dependency writes.'

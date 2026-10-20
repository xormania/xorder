#!/usr/bin/env bash
set -euo pipefail
# Keep CA validation and UID/GID handling identical to the other image lines.
exec bash /usr/local/bin/library-entrypoint bash /usr/local/bin/harness-session "$@"

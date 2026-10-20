#!/usr/bin/env bash
set -euo pipefail
# Check the prior volume ownership before the shared entrypoint can chown it.
# Isolated Python ignores HOME startup files and operator PYTHONPATH settings.
/usr/local/bin/python3 -I /usr/local/share/xorder/root_trust.py
# Keep CA validation and UID/GID handling identical to the other image lines.
exec bash /usr/local/bin/library-entrypoint bash /usr/local/bin/harness-session "$@"

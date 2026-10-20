#!/usr/bin/env bash
set -euo pipefail
# gosu selects /root for UID 0. This opt-in line deliberately preserves all
# operator account state in the private mounted HOME for every effective UID.
export HOME=/home/dev
export HARNESS_ROOT="${HARNESS_ROOT:-$HOME/.local/share/xorder/harnesses}"
export PATH="$HARNESS_ROOT/bin:$PATH"
export DISABLE_AUTOUPDATER=1 DISABLE_UPDATES=1 GROK_DISABLE_AUTOUPDATER=1
case "${HARNESS_AUTO_INSTALL:-1}" in
  0) ;;
  1)
    # Inspection and explicit management should never trigger unrelated installs.
    if [[ "${1:-}" != harnesses && "${1:-}" != /usr/local/bin/harnesses ]]; then
      read -r -a harness_names <<< "${HARNESS_NAMES:-codex claude grok}"
      harnesses ensure "${harness_names[@]}" >&2
    fi
    ;;
  *) echo 'HARNESS_AUTO_INSTALL must be 0 or 1' >&2; exit 64 ;;
esac
if [[ "$#" = 0 ]]; then set -- bash; fi
exec "$@"

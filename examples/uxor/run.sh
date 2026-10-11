#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
# Share the existing implementation and stack identities with the legacy entry point.
exec bash "$root/flowbite-xor/run.sh" "$@"

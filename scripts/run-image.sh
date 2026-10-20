#!/usr/bin/env bash
# Public invocation recipe, also used by behavioral checks.
set -euo pipefail
interactive=()
if [[ "${1:-}" = --interactive ]]; then
  interactive=(-it)
  shift
fi
image=${1:?Usage: run-image.sh IMAGE [COMMAND...]}
shift
workspace=${WORKSPACE:-$PWD}
cache=${CACHE_VOLUME:-image-library-cache}
if [ "$#" = 0 ]; then set -- bash; fi
trust=()
if [ -n "${CA_CERTIFICATE:-}" ]; then
  [[ "$CA_CERTIFICATE" = /* && -f "$CA_CERTIFICATE" && -r "$CA_CERTIFICATE" ]] || { echo 'CA_CERTIFICATE must be a readable absolute PEM file' >&2; exit 64; }
  trust=(--mount "type=bind,src=$CA_CERTIFICATE,dst=/run/library-proxy.pem,readonly" -e LIBRARY_CA_FILE=/run/library-proxy.pem)
fi
docker run --rm --init "${interactive[@]}" \
  --mount "type=bind,src=$workspace,dst=/workspace" \
  --mount "type=volume,src=$cache,dst=/home/dev" \
  -e PUID="${PUID:-$(id -u)}" -e PGID="${PGID:-$(id -g)}" \
  -e HTTP_PROXY -e HTTPS_PROXY -e NO_PROXY \
  -e HARNESS_AUTO_INSTALL -e HARNESS_NAMES \
  "${trust[@]}" \
  "$image" "$@"

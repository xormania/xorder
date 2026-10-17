#!/usr/bin/env bash
set -euo pipefail
# uv normally uses its bundled roots. The root entrypoint adds LIBRARY_CA_FILE
# to Debian's store before executing the workload, so opt in to that store only
# for these uv-bearing images and only when the caller has no explicit TLS choice.
if [ -n "${LIBRARY_CA_FILE:-}" ] &&
   [ -z "${UV_SYSTEM_CERTS+x}" ] && [ -z "${UV_NATIVE_TLS+x}" ] &&
   [ -z "${SSL_CERT_FILE+x}" ] && [ -z "${SSL_CERT_DIR+x}" ]; then
  export UV_SYSTEM_CERTS=true
fi
# Keep PEM validation, trust installation and PUID/PGID handling in one place.
exec bash "$(dirname -- "${BASH_SOURCE[0]}")/library-entrypoint" "$@"

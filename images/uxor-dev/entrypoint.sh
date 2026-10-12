#!/usr/bin/env bash
set -euo pipefail
uid=${PUID:-1000}; gid=${PGID:-1000}
[[ "$uid" =~ ^[0-9]+$ && "$gid" =~ ^[0-9]+$ ]] || exit 64
if [ "$(id -u)" = 0 ]; then
  # This profile's named cache volume, not the repository bind mount.
  chown -R "$uid:$gid" /app/demo/var
fi
cd /app/demo
exec bash /usr/local/bin/library-entrypoint sh /app/demo/frankenphp/docker-entrypoint.sh "$@"

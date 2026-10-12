#!/usr/bin/env bash
# Run from the installed consuming demo; never rewrite its configuration.
set -euo pipefail
cached=$(cat /opt/tailwind/version)
config=$(php bin/console debug:config symfonycasts_tailwind --format=json)
version=$(jq -r '(.symfonycasts_tailwind // .).binary_version // ""' <<< "$config")
binary=$(jq -r '(.symfonycasts_tailwind // .).binary // ""' <<< "$config")
platform=$(jq -r '(.symfonycasts_tailwind // .).binary_platform // "auto"' <<< "$config")
if [[ "$version" != "$cached" || -n "$binary" || ( "$platform" != auto && "$platform" != linux-x64 ) ]]; then
  echo "Tailwind cache not selected: project configuration differs from cached $cached"
  exit 0
fi
target="var/tailwind/$cached/tailwindcss-linux-x64"
mkdir -p "$(dirname "$target")"
if ! cmp -s /opt/tailwind/tailwindcss-linux-x64 "$target"; then
  install -m 755 /opt/tailwind/tailwindcss-linux-x64 "$target"
fi
echo "Seeded project Tailwind $cached from the verified image binary"

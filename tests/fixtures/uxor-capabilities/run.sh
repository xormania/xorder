#!/usr/bin/env bash
# Image tools work in the mounted checkout with an empty network namespace.
set -euo pipefail
npm ci --offline --ignore-scripts --no-audit --no-fund
npm test
cached=$(cat /opt/tailwind/version)
uxor-prime-tailwind
cmp /opt/tailwind/tailwindcss-linux-x64 "var/tailwind/$cached/tailwindcss-linux-x64"
rm -rf var/tailwind
for mismatch in version binary platform; do
  TAILWIND_FIXTURE_CASE="$mismatch" uxor-prime-tailwind
  test ! -e var/tailwind
done
printf '@import "tailwindcss";\n@source "./subject.html";\n' > input.css
tailwindcss --input input.css --output output.css --minify
node - <<'JS'
const assert = require('node:assert/strict');
const fs = require('node:fs');
const css = fs.readFileSync('output.css', 'utf8');
assert.match(css, /\.flex\{/);
assert.match(css, /display:flex/);
assert.match(css, /\.p-4\{/);
assert.match(css, /\.text-red-500\{/);
console.log('Prepared Tailwind binary compiled the owned utility subject');
JS

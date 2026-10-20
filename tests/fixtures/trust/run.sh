#!/usr/bin/env bash
# Verify single roots, CA bundles, real TLS clients and root/user execution.
set -euo pipefail
image=${1:?Supply image}
root=$(cd "$(dirname "$0")" && pwd)
work=$(mktemp -d)
servers=()
cleanup() {
  for server in "${servers[@]}"; do kill "$server" 2>/dev/null || true; wait "$server" 2>/dev/null || true; done
  if [ -d "$work/workspace" ]; then
    docker run --rm -e HARNESS_AUTO_INSTALL=0 -e PUID=0 -e PGID=0 --mount "type=bind,src=$work/workspace,dst=/workspace" "$image" \
      bash -c 'rm -f /workspace/root-proof; chown "$1:$2" /workspace' -- "$(id -u)" "$(id -g)" >/dev/null 2>&1 || true
  fi
  rm -rf "$work"
}
trap cleanup EXIT
for name in first second; do
  directory="$work/$name"
  mkdir -p "$directory/source"
  openssl req -x509 -newkey rsa:2048 -nodes -keyout "$directory/ca.key" -out "$directory/ca.crt" -days 1 \
    -subj "/CN=LibraryFixtureCA-$name" -addext basicConstraints=critical,CA:TRUE >/dev/null 2>&1
  openssl req -newkey rsa:2048 -nodes -keyout "$directory/server.key" -out "$directory/server.csr" -subj /CN=localhost >/dev/null 2>&1
  printf 'subjectAltName=DNS:localhost,IP:127.0.0.1\n' > "$directory/server.ext"
  openssl x509 -req -in "$directory/server.csr" -CA "$directory/ca.crt" -CAkey "$directory/ca.key" -CAcreateserial \
    -out "$directory/server.crt" -days 1 -extfile "$directory/server.ext" >/dev/null 2>&1
  git -C "$directory/source" init -q
  git -C "$directory/source" -c user.name=Fixture -c user.email=fixture@example.test commit --allow-empty -qm Fixture
  git clone --bare -q "$directory/source" "$directory/repo.git"
  git -C "$directory/repo.git" update-server-info
  printf 'trusted\n' > "$directory/proof.txt"
  python3 "$root/uv-packages.py" "$directory" "$name"
  python3 "$root/server.py" "$directory" > "$directory/server.log" 2>&1 & servers+=("$!")
  for attempt in {1..50}; do [ ! -f "$directory/port" ] || break; sleep .1; done
  port=$(cat "$directory/port")
  python3 - "$directory" "$port" "$name" <<'PY'
import json, sys, zipfile
from pathlib import Path
root=Path(sys.argv[1]); url=f'https://localhost:{sys.argv[2]}'; name='fixture/proof-'+sys.argv[3]
with zipfile.ZipFile(root/'package.zip', 'w') as archive:
    archive.writestr('proof.txt', 'Composer downloaded this over verified HTTPS.\n')
package={'name':name,'version':'1.0.0','type':'library','dist':{'type':'zip','url':url+'/package.zip'}}
(root/'packages.json').write_text(json.dumps({'packages':{name:{'1.0.0':package}}}))
PY
done
first_port=$(cat "$work/first/port")
second_port=$(cat "$work/second/port")
docker run --rm -e HARNESS_AUTO_INSTALL=0 --network host \
  --mount "type=bind,src=$root/uv-clients.sh,dst=/run/trust-uv-clients.sh,readonly" \
  "$image" bash -c '
  set -euo pipefail
  if curl --fail --silent "https://localhost:$1/proof.txt"; then
    echo "An HTTPS origin was trusted without its CA" >&2; exit 1
  fi
  bash /run/trust-uv-clients.sh untrusted "https://localhost:$1" "https://localhost:$2"
  ' -- "$first_port" "$second_port"
# A single root still works, and cannot trust the independently signed server.
docker run --rm -e HARNESS_AUTO_INSTALL=0 --network host -e LIBRARY_CA_FILE=/run/ca.pem \
  --mount "type=bind,src=$work/first/ca.crt,dst=/run/ca.pem,readonly" \
  --mount "type=bind,src=$root/uv-clients.sh,dst=/run/trust-uv-clients.sh,readonly" "$image" bash -c '
  set -euo pipefail
  test "$(id -u)" = 1000
  curl --fail --silent "https://localhost:$1/proof.txt" | rg "^trusted$"
  if curl --fail --silent "https://localhost:$2/proof.txt"; then
    echo "An independently signed HTTPS origin was trusted with the wrong CA" >&2; exit 1
  fi
  bash /run/trust-uv-clients.sh single "https://localhost:$1" "https://localhost:$2"
  ' -- "$first_port" "$second_port"
cat "$work/first/ca.crt" "$work/second/ca.crt" > "$work/bundle.pem"
# Both independently signed origins must work for every advertised TLS client.
docker run --rm -e HARNESS_AUTO_INSTALL=0 --network host -e LIBRARY_CA_FILE=/run/ca.pem \
  --mount "type=bind,src=$work/bundle.pem,dst=/run/ca.pem,readonly" \
  --mount "type=bind,src=$root/clients.sh,dst=/run/trust-clients.sh,readonly" \
  --mount "type=bind,src=$root/uv-clients.sh,dst=/run/trust-uv-clients.sh,readonly" \
  "$image" bash /run/trust-clients.sh "https://localhost:$first_port" "https://localhost:$second_port"
# Exercise uv's isolated build after the same root entrypoint retains UID 0.
docker run --rm -e HARNESS_AUTO_INSTALL=0 --network host -e PUID=0 -e PGID=0 -e LIBRARY_CA_FILE=/run/ca.pem \
  --mount "type=bind,src=$work/bundle.pem,dst=/run/ca.pem,readonly" \
  --mount "type=bind,src=$root/uv-clients.sh,dst=/run/trust-uv-clients.sh,readonly" \
  "$image" bash -c 'set -euo pipefail; test "$(id -u)" = 0; exec bash /run/trust-uv-clients.sh trusted "$@"' \
  -- "https://localhost:$first_port" "https://localhost:$second_port"
# Repeating setup in the same root container removes roots omitted from the new
# bundle, including the old image's single-file layout, without stale trust.
docker run --rm -e HARNESS_AUTO_INSTALL=0 --network host -e PUID=0 -e PGID=0 -e LIBRARY_CA_FILE=/run/ca.pem \
  --mount "type=bind,src=$work/bundle.pem,dst=/run/ca.pem,readonly" \
  --mount "type=bind,src=$work/first/ca.crt,dst=/run/single.pem,readonly" \
  --mount "type=bind,src=$work/second/ca.crt,dst=/run/second.pem,readonly" "$image" bash -c '
  certificates=(/usr/local/share/ca-certificates/library-proxy/*.crt)
  test "${#certificates[@]}" = 2
  cp "${certificates[1]}" /usr/local/share/ca-certificates/library-proxy.crt
  LIBRARY_CA_FILE=/run/second.pem bash /usr/local/bin/library-entrypoint true
  # CApath-only verification catches stale subject-hash links when a file is
  # replaced in place. The certificate bundle alone would hide that problem.
  openssl s_client -verify_return_error -CApath /etc/ssl/certs -no-CAfile -no-CAstore \
    -connect "localhost:$2" </dev/null >/dev/null 2>&1
  ! curl --fail --silent "https://localhost:$1/proof.txt"
  LIBRARY_CA_FILE=/run/single.pem bash /usr/local/bin/library-entrypoint true
  certificates=(/usr/local/share/ca-certificates/library-proxy/*.crt)
  test "${#certificates[@]}" = 1
  test ! -e /usr/local/share/ca-certificates/library-proxy.crt
  curl --fail --silent "https://localhost:$1/proof.txt" | rg "^trusted$"
  ! curl --fail --silent "https://localhost:$2/proof.txt"
  LIBRARY_CA_FILE=/run/single.pem bash /usr/local/bin/library-entrypoint true
  curl --fail --silent "https://localhost:$1/proof.txt" | rg "^trusted$"
  test -z "$(find /tmp -maxdepth 1 -name '\''library-ca.*'\'' -print -quit)"
  ' -- "$first_port" "$second_port"
printf 'invalid\n' > "$work/bad.pem"
: > "$work/empty.pem"
cat "$work/first/ca.crt" > "$work/mixed.pem"
printf '%s\n' '-----BEGIN CERTIFICATE-----' 'not-a-certificate' '-----END CERTIFICATE-----' >> "$work/mixed.pem"
cat "$work/first/ca.crt" > "$work/truncated.pem"
printf '%s\n' '-----BEGIN CERTIFICATE-----' 'truncated' >> "$work/truncated.pem"
for invalid in bad empty mixed truncated; do
  if docker run --rm -e HARNESS_AUTO_INSTALL=0 -e LIBRARY_CA_FILE=/run/ca.pem --mount "type=bind,src=$work/$invalid.pem,dst=/run/ca.pem,readonly" "$image" true; then
    echo "$invalid certificate bundle was accepted" >&2; exit 1
  fi
done
if docker run --rm -e HARNESS_AUTO_INSTALL=0 --user 1000 -e LIBRARY_CA_FILE=/run/ca.pem --mount "type=bind,src=$work/bundle.pem,dst=/run/ca.pem,readonly" "$image" true; then
  echo 'A non-root entrypoint silently ignored system trust setup' >&2; exit 1
fi
mkdir "$work/workspace"
docker run --rm -e HARNESS_AUTO_INSTALL=0 -e PUID=0 -e PGID=0 --mount "type=bind,src=$work/workspace,dst=/workspace" "$image" bash -c 'chown 0:0 /workspace; chmod 755 /workspace; touch root-proof; test "$(id -u)" = 0'
test "$(stat -c %u "$work/workspace/root-proof")" = 0
echo 'Single and bundled CAs, TLS clients, repeated setup, validation errors and PUID=0 passed'

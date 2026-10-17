#!/usr/bin/env bash
set -euo pipefail
first=${1:?Supply first independently signed HTTPS origin}
second=${2:?Supply second independently signed HTTPS origin}
test "$(id -u)" = 1000
certificates=(/usr/local/share/ca-certificates/library-proxy/*.crt)
test "${#certificates[@]}" = 2
for certificate in "${certificates[@]}"; do
  test "$(grep -c -- '-----BEGIN CERTIFICATE-----' "$certificate")" = 1
  openssl x509 -in "$certificate" -noout
done
bash /run/trust-uv-clients.sh trusted "$first" "$second"
curl --fail --silent "$first/proof.txt" | rg '^trusted$'
curl --fail --silent "$second/proof.txt" | rg '^trusted$'
git clone -q "$first/repo.git" "$HOME/proof-repo-first"
git clone -q "$second/repo.git" "$HOME/proof-repo-second"
if command -v composer >/dev/null; then
  mkdir "$HOME/composer-tls"; cd "$HOME/composer-tls"
  php -r 'echo json_encode(["repositories"=>[["type"=>"composer","url"=>$argv[1]],["type"=>"composer","url"=>$argv[2]],["packagist.org"=>false]],"require"=>["fixture/proof-first"=>"1.0.0","fixture/proof-second"=>"1.0.0"]]);' "$first" "$second" > composer.json
  # install audits only when requested; it has no --no-audit option. Keep
  # Packagist disabled above so this fixture uses only its own TLS origins.
  composer install --no-interaction --no-progress
  test -f vendor/fixture/proof-first/proof.txt
  test -f vendor/fixture/proof-second/proof.txt
fi
if command -v node >/dev/null; then
  node -e '
  const https = require("https");
  Promise.all(process.argv.slice(1).map(url => new Promise((resolve, reject) => {
    https.get(url, response => {
      if (response.statusCode !== 200) return reject(new Error(`Unexpected status ${response.statusCode}`));
      response.resume(); response.on("end", resolve); response.on("error", reject);
    }).on("error", reject);
  }))).catch(error => { console.error(error); process.exit(1); });
  ' "$first/proof.txt" "$second/proof.txt"
fi

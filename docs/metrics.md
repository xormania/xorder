# Verified release measurements

Generated from the verified release ledger. Sizes describe local Docker images, not registry transfer sizes. Comparisons use the same size method and image store. Build and verification times describe the recorded publication run, including its cache and runner conditions; they are not performance guarantees.

| Line | Revision | Platform | Image size (MiB) | Baseline size (MiB) | Size change | Build (s) | Public verification (s) |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| [harness-live/trixie](images/harness-live-trixie.md) | 1.0.0 | linux/amd64 | 676.7 | — | — | 50.36 | 65.91 |
| [php-browser/8.4-trixie](images/php-browser-8.4-trixie.md) | 1.2.3 | linux/amd64 | 1,620.2 | 1,618.8 (v1.2.2) | +0.1% | 59.59 | 30.42 |
| [php-browser/8.5-trixie](images/php-browser-8.5-trixie.md) | 1.2.3 | linux/amd64 | 1,650.0 | 1,648.6 (v1.2.2) | +0.1% | 60.82 | 25.92 |
| [php-dev/8.4-trixie](images/php-dev-8.4-trixie.md) | 1.2.3 | linux/amd64 | 913.7 | 912.4 (v1.2.2) | +0.2% | 180.94 | 30.07 |
| [php-dev/8.5-trixie](images/php-dev-8.5-trixie.md) | 1.2.3 | linux/amd64 | 943.6 | 942.2 (v1.2.2) | +0.1% | 173.91 | 25.31 |
| [php-frankenphp/8.4-trixie](images/php-frankenphp-8.4-trixie.md) | 1.1.4 | linux/amd64 | 965.0 | 963.6 (v1.1.3) | +0.1% | 169.42 | 30.46 |
| [php-frankenphp/8.5-trixie](images/php-frankenphp-8.5-trixie.md) | 1.1.4 | linux/amd64 | 994.7 | 993.3 (v1.1.3) | +0.1% | 199.37 | 30.75 |
| [php-serena/8.5-trixie](images/php-serena-8.5-trixie.md) | 1.1.3 | linux/amd64 | 1,245.1 | 1,243.7 (v1.1.2) | +0.1% | 39.42 | 91.34 |
| [php-toolkit/8.4-trixie](images/php-toolkit-8.4-trixie.md) | 1.0.3 | linux/amd64 | 938.2 | 936.8 (v1.0.2) | +0.1% | 12.00 | 38.79 |
| [php-toolkit/8.5-trixie](images/php-toolkit-8.5-trixie.md) | 1.0.3 | linux/amd64 | 968.0 | 966.6 (v1.0.2) | +0.1% | 13.12 | 32.11 |
| [playwright-browser/1.58-trixie](images/playwright-browser-1.58-trixie.md) | 1.0.4 | linux/amd64 | 2,213.9 | 2,213.9 (v1.0.3) | +0.0% | Not measured | 165.35 |
| [python-dev/3.14-trixie](images/python-dev-3.14-trixie.md) | 1.1.4 | linux/amd64 | 583.7 | 585.5 (v1.1.3) | -0.3% | 46.35 | 23.57 |
| [python-matrix/trixie](images/python-matrix-trixie.md) | 1.0.0 | linux/amd64 | 852.4 | — | — | 43.85 | 112.93 |
| [rust-dev/1.99-trixie](images/rust-dev-1.99-trixie.md) | 1.1.4 | linux/amd64 | 1,274.9 | 1,274.9 (v1.1.3) | +0.0% | 52.51 | 11.68 |
| [uxor-dev/8.4-trixie](images/uxor-dev-8.4-trixie.md) | 1.0.2 | linux/amd64 | 1,201.6 | 1,200.2 (v1.0.1) | +0.1% | 28.81 | 261.46 |
| [uxor-dev/8.5-trixie](images/uxor-dev-8.5-trixie.md) | 1.0.2 | linux/amd64 | 1,231.3 | 1,229.9 (v1.0.1) | +0.1% | Not measured | 348.61 |

Image/release pages retain exact bytes, artifact identities, measurement methods, cache inputs and evidence links. Older records without measurements remain valid and are omitted from this table.

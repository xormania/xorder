# Python compatibility matrix

`python-matrix/trixie` supplies Python 3.10, 3.12 and 3.14, uv, native build
tools, PostgreSQL clients and tmux 3.x. Interpreters are installed while building
the image, outside the persistent home volume, and are invoked explicitly as
`python3.10`, `python3.12` and `python3.14`. Starting a container does not download
an interpreter. The measured release inventory records every exact Python and
SQLite version and tmux's version.

Exact patch selections live in [`versions.json`](../images/python-matrix/versions.json).
All three named interpreters are installed by the parent's pinned uv under
`/opt/xorder/python`, with commands in `/opt/xorder/python-bin`. The parent's
default `python` and `python3` commands and pip installation remain intact;
parent refreshes do not silently change the matrix's explicitly selected patches.

The definition remains unavailable until publication produces an accepted
release record. Choose its verified digest from the [catalog](../catalog.json)
once available; do not guess a tag from the line name. This is a general
compatibility environment, with no xordination broker, vendor CLI, or account
state installed.

Python 3.10 reached [upstream end of life on October 1, 2026](https://peps.python.org/pep-0619/#3-10-lifespan).
It is included for compatibility testing. An image release group's support
period does not extend Python's upstream security support.

## Run a project matrix

Mount the checkout using the normal [workspace and proxy recipe](usage.md),
and select each interpreter for both selection and execution:

```sh
export IMAGE='<accepted python-matrix digest_reference>'
export WORKSPACE='/absolute/path/to/xordination'
for version in 3.10 3.12 3.14; do
  bash scripts/run-image.sh "$IMAGE" bash -eu -c '
    python"$1" scripts/ci/select_checks.py --event workflow_dispatch --selection-file /tmp/selection.json
    PYTHONPATH=src python"$1" scripts/ci/run_contracts.py --selection /tmp/selection.json
  ' bash "$version"
done
bash scripts/run-image.sh "$IMAGE" python3.14 scripts/testing/live_tmux.py self-check
```

Those are the consumer's own standard-library contract commands. They require
no installed project dependencies, vendor credentials or model calls. Other
projects retain their own lockfiles and dependency installation instructions.

## Readiness evidence

```sh
bash scripts/verify-image.sh 'python-matrix/trixie' "$IMAGE"
```

The readiness recipe first fetches xordination at the exact commit in
[`consumer.json`](../tests/fixtures/python-matrix/consumer.json) on the Docker
host. This preparation needs GitHub network access. It then mounts that disposable
checkout and runs the acceptance workload with `--network=none`:

- Each explicitly named interpreter demonstrates SQLite WAL mode, a URI
  read-only connection reading committed WAL data, rejection of a write, and
  creation of a virtual environment with usable pip without downloading files.
- Each interpreter runs full contract selection and execution. Its execution
  census must show all 145 pinned contracts collected, started and executed,
  with none skipped or unexercised.
- The real tmux executable runs the consumer launcher's `self-check` on its
  private socket. No broker, harness sign-in, vendor CLI or model is needed.
- The configured workspace user compiles and runs a native C program.

`out/python-matrix/acceptance.json` records interpreter identity, SQLite versions,
contract counts, tmux version and self-check results. Per-interpreter contract
reports remain alongside it. These validation artifacts establish readiness of
the tested image; published image identity and availability still come from the
normal release records.

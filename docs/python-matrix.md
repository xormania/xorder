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
compatibility environment, with no project broker, vendor CLI, or account
state installed.

Python 3.10 reached [upstream end of life on October 1, 2026](https://peps.python.org/pep-0619/#3-10-lifespan).
It is included for compatibility testing. An image release group's support
period does not extend Python's upstream security support.

## Run a project matrix

Mount the checkout using the normal [workspace and proxy recipe](usage.md),
and select each interpreter explicitly. For a project with standard-library
unit tests, for example:

```sh
export IMAGE='<accepted python-matrix digest_reference>'
export WORKSPACE='/absolute/path/to/project'
for version in 3.10 3.12 3.14; do
  bash scripts/run-image.sh "$IMAGE" bash -eu -c '
    python"$1" -m unittest discover -s tests -v
  ' bash "$version"
done
```

The project owns test selection, dependency lockfiles, preparation and application
acceptance. Replace that example command with its documented test command and
install any project dependencies into a project-owned environment.

## Readiness evidence

```sh
bash scripts/verify-image.sh 'python-matrix/trixie' "$IMAGE"
```

The readiness recipe mounts a disposable empty workspace, a fresh persistent HOME
volume and Xorder-owned fixtures. It runs the complete acceptance workload with
`--network=none`; no consumer checkout or project dependencies are required:

- Each explicitly named interpreter demonstrates SQLite WAL mode, a URI
  read-only connection reading committed WAL data, rejection of a write, and
  creation of a virtual environment with usable pip without downloading files.
  Pip installs a tiny Xorder-owned local wheel with `--no-index --no-deps`, and
  the environment imports and executes the installed module.
- Each interpreter writes and reads files as the configured user under both
  mounted `/workspace` and `/home/dev`, reads its own `/proc` identity, exchanges data in both
  directions through a PTY, and completes a request/response over a Unix socket.
- Each interpreter invokes real tmux on a private socket, creates a session,
  sends shell input, captures executed output and confirms session cleanup.
- The configured workspace user compiles and runs a native C program.

`out/python-matrix/acceptance.json` records interpreter identity, SQLite and pip
versions, offline install results and terminal/socket operations. Its schema-2
evidence identifies the Xorder capability fixture; historical consumer-based
release evidence remains unchanged. These validation artifacts establish
readiness of the tested image; published image identity and availability still
come from the normal release records. Fixture changes do not change image bytes
or allocate a replacement image revision.

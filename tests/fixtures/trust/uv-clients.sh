#!/usr/bin/env bash
set -euo pipefail
mode=${1:?Supply trusted, single or untrusted}
first=${2:?Supply backend HTTPS origin}
second=${3:?Supply proof HTTPS origin}
command -v uv >/dev/null || exit 0
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
export UV_NO_CACHE=1 UV_PYTHON_DOWNLOADS=never UV_NO_PROGRESS=1
python=$(command -v python3)
if [ "$mode" = untrusted ] || [ "$mode" = single ]; then
  uv venv --python "$python" "$work/venv"
  rejected_index="$first/simple"
  rejected_package=fixture-uv-backend
  if [ "$mode" = single ]; then
    uv pip install --python "$work/venv/bin/python" --default-index "$first/simple" fixture-uv-backend==1.0.0
    "$work/venv/bin/python" -c 'import fixture_uv_backend; assert callable(fixture_uv_backend.build_wheel)'
    rejected_index="$second/simple"
    rejected_package=fixture-uv-proof
  fi
  if uv pip install --python "$work/venv/bin/python" --default-index "$rejected_index" \
      "$rejected_package==1.0.0" >"$work/error" 2>&1; then
    echo 'uv unexpectedly trusted the private HTTPS origin without its CA' >&2; exit 1
  fi
  # An unrelated resolution or routing error must not count as a TLS rejection.
  rg -i 'invalid peer certificate|unknownissuer|certificate verify failed' "$work/error"
  exit 0
fi
test "$mode" = trusted
cd "$work"
cat > pyproject.toml <<'TOML'
[project]
name = "fixture-uv-project"
version = "1.0.0"
requires-python = ">=3.11"
dependencies = ["fixture-uv-proof==1.0.0"]

[build-system]
requires = ["fixture-uv-backend==1.0.0"]
build-backend = "fixture_uv_backend"
TOML
# These commands use independent disposable caches. sync therefore resolves and
# downloads build-system.requires again instead of reusing lock's backend wheel.
uv lock --python "$python" --default-index "$first/simple" --index "$second/simple"
cp uv.lock locked-before
uv sync --locked --no-editable --python "$python" --default-index "$first/simple" --index "$second/simple"
cmp uv.lock locked-before
.venv/bin/python -c 'from fixture_uv_project import PROOF, BUILT; assert PROOF == "independent HTTPS wheel"; assert BUILT == "isolated HTTPS backend"'
echo "uv private HTTPS resolution, locked isolated build and install passed as UID $(id -u)"

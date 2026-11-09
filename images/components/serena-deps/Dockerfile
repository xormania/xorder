# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:0.12.8@sha256:d1cbaeadc234fe19c0d93daabcf5e98738cd93c6d1dd4918ef6aa30735feb23a AS uv
FROM docker.io/library/python:3.12.12-slim-trixie@sha256:f3fa41d74a768c2fce8016b98c191ae8c1bacd8f1152870a3f9f87d350920b7c AS dependencies
ARG APT_REFRESH
COPY --from=uv /uv /usr/local/bin/uv
# uv fetches the Serena git pin through git; the package has Python source only.
RUN --mount=type=cache,target=/var/cache/apt \
    test -n "$APT_REFRESH" && apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
COPY images/php-mago-serena/serena/pyproject.toml images/php-mago-serena/serena/uv.lock /opt/xorder/serena/
COPY images/php-mago-serena/serena/adapter/pyproject.toml /opt/xorder/serena/adapter/pyproject.toml
COPY images/php-mago-serena/serena/adapter-build-requirements.txt /opt/xorder/serena/adapter-build-requirements.txt
RUN --mount=type=secret,id=xorder_ca \
    set -eu; \
    if [ -s /run/secrets/xorder_ca ]; then export SSL_CERT_FILE=/run/secrets/xorder_ca GIT_SSL_CAINFO=/run/secrets/xorder_ca; fi; \
    UV_PYTHON_DOWNLOADS=never UV_PROJECT_ENVIRONMENT=/opt/venv \
      uv --no-cache sync --project /opt/xorder/serena --frozen --no-dev --no-install-workspace --python /usr/local/bin/python3 \
    && uv --no-cache pip install --python /opt/venv/bin/python --require-hashes --only-binary :all: -r /opt/xorder/serena/adapter-build-requirements.txt \
    && uv pip check --python /opt/venv/bin/python \
    && rm -rf /root/.cache/uv
FROM scratch
COPY --from=dependencies /usr/local /payload/python
COPY --from=dependencies /opt/venv /payload/venv

# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:0.12.8@sha256:d1cbaeadc234fe19c0d93daabcf5e98738cd93c6d1dd4918ef6aa30735feb23a AS uv
FROM docker.io/library/python:3.12.12-slim-trixie@sha256:f3fa41d74a768c2fce8016b98c191ae8c1bacd8f1152870a3f9f87d350920b7c AS dependencies
ARG APT_REFRESH
COPY --from=uv /uv /usr/local/bin/uv
# Patch only dependency pins before building the reviewed Serena source.
RUN --mount=type=cache,target=/var/cache/apt \
    test -n "$APT_REFRESH" && apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
COPY images/php-mago-serena/serena/pyproject.toml images/php-mago-serena/serena/uv.lock /opt/xorder/serena/
COPY images/php-mago-serena/serena/security.patch /opt/xorder/serena/security.patch
COPY images/php-mago-serena/serena/adapter/pyproject.toml /opt/xorder/serena/adapter/pyproject.toml
COPY images/php-mago-serena/serena/adapter-build-requirements.txt /opt/xorder/serena/adapter-build-requirements.txt
RUN --mount=type=secret,id=xorder_ca \
    set -eu; \
    if [ -s /run/secrets/xorder_ca ]; then export SSL_CERT_FILE=/run/secrets/xorder_ca GIT_SSL_CAINFO=/run/secrets/xorder_ca; fi; \
    git init /opt/xorder/serena/upstream \
    && git -C /opt/xorder/serena/upstream remote add origin https://github.com/oraios/serena.git \
    && git -C /opt/xorder/serena/upstream fetch --depth=1 origin ede329aaf0c824bea75455a2926f01420d7aa620 \
    && git -C /opt/xorder/serena/upstream checkout --detach FETCH_HEAD \
    && test "$(git -C /opt/xorder/serena/upstream rev-parse HEAD)" = ede329aaf0c824bea75455a2926f01420d7aa620 \
    && git -C /opt/xorder/serena/upstream apply --check /opt/xorder/serena/security.patch \
    && git -C /opt/xorder/serena/upstream apply /opt/xorder/serena/security.patch \
    && git -C /opt/xorder/serena/upstream rev-parse HEAD > /opt/xorder/serena/serena-source.sha \
    && sha256sum /opt/xorder/serena/upstream/pyproject.toml > /opt/xorder/serena/serena-manifest.sha256 \
    && UV_PYTHON_DOWNLOADS=never UV_PROJECT_ENVIRONMENT=/opt/venv \
      uv --no-cache sync --project /opt/xorder/serena --locked --no-dev --no-install-workspace --no-editable --python /usr/local/bin/python3 \
    && uv --no-cache pip install --python /opt/venv/bin/python --require-hashes --only-binary :all: -r /opt/xorder/serena/adapter-build-requirements.txt \
    && uv pip check --python /opt/venv/bin/python \
    && sha256sum --check /opt/xorder/serena/serena-manifest.sha256 \
    && rm -rf /root/.cache/uv
FROM scratch
COPY --from=dependencies /usr/local /payload/python
COPY --from=dependencies /opt/venv /payload/venv
COPY --from=dependencies /opt/xorder/serena/serena-source.sha /opt/xorder/serena/serena-manifest.sha256 /payload/identity/

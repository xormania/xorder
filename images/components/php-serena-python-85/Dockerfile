# syntax=docker/dockerfile:1.7
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
# Keep the proven Agentscient v2 REPL/PHPactor pair. The PHP/Trixie parent
# supplies Debian Python and mbstring; the final image uses this same native donor.
COPY --from=ghcr.io/astral-sh/uv:0.12.19@sha256:04d046b13e60d6bcec73cbc5e1cad25d680dea90c8573340950a0ac2d1aef424 /uv /usr/local/bin/uv
COPY images/php-serena/requirements-build.txt /opt/xorder/serena/requirements-build.txt
COPY images/php-serena/security.patch images/php-serena/security-uv.lock /opt/xorder/serena/
RUN --mount=type=secret,id=xorder_ca \
    set -eu; \
    if [ -s /run/secrets/xorder_ca ]; then export GIT_SSL_CAINFO=/run/secrets/xorder_ca SSL_CERT_FILE=/run/secrets/xorder_ca UV_SYSTEM_CERTS=true; fi; \
    git init /opt/serena-source \
    && git -C /opt/serena-source remote add origin https://github.com/oraios/serena.git \
    && git -C /opt/serena-source fetch --depth=1 origin b79e2a55f9d4072084977dd35bd07d31146d88b9 \
    && git -C /opt/serena-source checkout --detach FETCH_HEAD \
    && test "$(git -C /opt/serena-source rev-parse HEAD)" = b79e2a55f9d4072084977dd35bd07d31146d88b9 \
    && echo '66eb88aeaede6679cd0f79782ccdfc1afb3558be12a202a68059fb62637b880e  /opt/serena-source/uv.lock' | sha256sum --check \
    && cp /opt/serena-source/uv.lock /opt/xorder/serena/upstream-uv.lock \
    && git -C /opt/serena-source apply --check /opt/xorder/serena/security.patch \
    && git -C /opt/serena-source apply /opt/xorder/serena/security.patch \
    && cp /opt/xorder/serena/security-uv.lock /opt/serena-source/uv.lock \
    && sha256sum /opt/serena-source/pyproject.toml > /opt/xorder/serena/patched-manifest.sha256 \
    && uv --no-cache venv --python /usr/bin/python3 /opt/serena-env \
    && uv --no-cache pip install --python /opt/serena-env/bin/python \
        --require-hashes --only-binary :all: -r /opt/xorder/serena/requirements-build.txt \
    && UV_PROJECT_ENVIRONMENT=/opt/serena-env UV_PYTHON_DOWNLOADS=never \
        uv --no-cache sync --project /opt/serena-source --python /usr/bin/python3 \
        --locked --no-dev --no-editable --no-build-isolation \
    && uv pip check --python /opt/serena-env/bin/python \
    && sha256sum --check /opt/xorder/serena/patched-manifest.sha256 \
    && cmp /opt/xorder/serena/security-uv.lock /opt/serena-source/uv.lock

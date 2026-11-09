# syntax=docker/dockerfile:1.7
ARG DOWNLOAD_PYTHON_IMAGE
FROM ${DOWNLOAD_PYTHON_IMAGE}
COPY scripts/fetch_build_input.py /opt/xorder/build-tools/
COPY scripts/xorder/download_cache.py scripts/xorder/transport.py /opt/xorder/build-tools/xorder/
ARG PHPACTOR_URL
ARG PHPACTOR_SHA256
RUN --mount=type=secret,id=xorder_ca \
    --mount=type=cache,id=xorder-php-portable-downloads,target=/var/cache/xorder-downloads \
    set -eu; \
    if [ -s /run/secrets/xorder_ca ]; then export SSL_CERT_FILE=/run/secrets/xorder_ca; fi; \
    python3 /opt/xorder/build-tools/fetch_build_input.py \
      --url "$PHPACTOR_URL" --sha256 "$PHPACTOR_SHA256" \
      --destination /payload/phpactor.phar --cache-dir /var/cache/xorder-downloads \
    && chmod 0644 /payload/phpactor.phar

# syntax=docker/dockerfile:1.7
ARG DOWNLOAD_PYTHON_IMAGE
FROM ${DOWNLOAD_PYTHON_IMAGE}
COPY scripts/fetch_build_input.py /opt/xorder/build-tools/
COPY scripts/xorder/download_cache.py scripts/xorder/transport.py /opt/xorder/build-tools/xorder/
ARG SYMFONY_URL
ARG SYMFONY_SHA256
RUN --mount=type=secret,id=xorder_ca \
    --mount=type=cache,id=xorder-php-portable-downloads,target=/var/cache/xorder-downloads \
    set -eu; \
    if [ -s /run/secrets/xorder_ca ]; then export SSL_CERT_FILE=/run/secrets/xorder_ca; fi; \
    python3 /opt/xorder/build-tools/fetch_build_input.py \
      --url "$SYMFONY_URL" --sha256 "$SYMFONY_SHA256" \
      --destination /tmp/symfony.tar.gz --cache-dir /var/cache/xorder-downloads \
    && mkdir -p /payload/infection \
    && tar -xzf /tmp/symfony.tar.gz -C /payload symfony \
    && chmod 0755 /payload/symfony \
    && rm /tmp/symfony.tar.gz
ARG INFECTION_URL
ARG INFECTION_SHA256
RUN --mount=type=secret,id=xorder_ca \
    --mount=type=cache,id=xorder-php-portable-downloads,target=/var/cache/xorder-downloads \
    set -eu; \
    if [ -s /run/secrets/xorder_ca ]; then export SSL_CERT_FILE=/run/secrets/xorder_ca; fi; \
    python3 /opt/xorder/build-tools/fetch_build_input.py \
      --url "$INFECTION_URL" --sha256 "$INFECTION_SHA256" \
      --destination /payload/infection/infection.phar --cache-dir /var/cache/xorder-downloads \
    && chmod 0644 /payload/infection/infection.phar

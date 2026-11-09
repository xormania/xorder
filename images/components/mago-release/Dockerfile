# syntax=docker/dockerfile:1
FROM docker.io/library/python:3.12.12-slim-trixie@sha256:f3fa41d74a768c2fce8016b98c191ae8c1bacd8f1152870a3f9f87d350920b7c AS fetch
ARG MAGO_VERSION
ARG MAGO_SHA256
COPY scripts/fetch_build_input.py /opt/xorder/tools/fetch_build_input.py
COPY scripts/xorder/download_cache.py scripts/xorder/transport.py /opt/xorder/tools/xorder/
RUN --mount=type=cache,target=/root/.cache/xorder/build-downloads \
    --mount=type=secret,id=xorder_ca \
    set -eu; \
    if [ -s /run/secrets/xorder_ca ]; then export SSL_CERT_FILE=/run/secrets/xorder_ca; fi; \
    python3 /opt/xorder/tools/fetch_build_input.py \
      --url "https://github.com/carthage-software/mago/releases/download/${MAGO_VERSION}/mago-${MAGO_VERSION}-x86_64-unknown-linux-gnu.tar.gz" \
      --sha256 "$MAGO_SHA256" --destination /tmp/mago.tar.gz \
    && mkdir -p /payload/bin /payload/licenses /unpack \
    && tar -xzf /tmp/mago.tar.gz -C /unpack \
    && cp "/unpack/mago-${MAGO_VERSION}-x86_64-unknown-linux-gnu/mago" /payload/bin/mago \
    && chmod 0755 /payload/bin/mago \
    && cp "/unpack/mago-${MAGO_VERSION}-x86_64-unknown-linux-gnu/LICENSE-MIT" "/unpack/mago-${MAGO_VERSION}-x86_64-unknown-linux-gnu/LICENSE-APACHE" /payload/licenses/ \
    && /payload/bin/mago --version > /payload/version.txt
FROM scratch
COPY --from=fetch /payload /payload

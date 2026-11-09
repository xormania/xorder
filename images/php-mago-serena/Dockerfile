# syntax=docker/dockerfile:1
ARG BASE_IMAGE
FROM docker.io/library/python:3.12.12-slim-trixie@sha256:f3fa41d74a768c2fce8016b98c191ae8c1bacd8f1152870a3f9f87d350920b7c AS python
FROM ghcr.io/astral-sh/uv:0.12.8@sha256:d1cbaeadc234fe19c0d93daabcf5e98738cd93c6d1dd4918ef6aa30735feb23a AS uv
FROM docker.io/library/rust:1.99.0-bookworm@sha256:114c7a4425406451c2866b6aafe69fe29b1b298832db1277d411ac73c82d04d6 AS mago-build
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ARG MAGO_BUILD_JOBS=4
ARG MAGO_NATIVE_TESTS=0
WORKDIR /src
RUN --mount=type=secret,id=xorder_ca \
    set -eu; \
    if [ -s /run/secrets/xorder_ca ]; then export GIT_SSL_CAINFO=/run/secrets/xorder_ca; fi; \
    git init . && git remote add origin https://github.com/carthage-software/mago.git \
    && git fetch --depth 1 origin 46df50c96d93d0ac3655c116c375574277cf0b30 \
    && git checkout --detach FETCH_HEAD \
    && test "$(git rev-parse HEAD)" = 46df50c96d93d0ac3655c116c375574277cf0b30
COPY images/php-mago-serena/serena/patches/mago-lsp-extensions.patch /candidate.patch
RUN printf '%s\n' 'ca955e0db6023a997fe708d46d3bd0b92e6dd91237aee7c206f13768effdea11  /candidate.patch' > /patch.sha256 \
    && sha256sum --check --strict /patch.sha256 \
    && git apply --check /candidate.patch && git apply /candidate.patch \
    && git diff --exit-code -- Cargo.lock composer crates/extension/src/protocol.rs \
    && printf '%s\n' 'f5468183e5440ccacff66b06f7b444f15641caf89d9533057a03e4f280a28e1d  Cargo.lock' > /lock.sha256 \
    && sha256sum --check --strict /lock.sha256
RUN --mount=type=cache,target=/usr/local/cargo/registry \
    --mount=type=cache,target=/src/target \
    --mount=type=secret,id=xorder_ca \
    set -eu; \
    if [ -s /run/secrets/xorder_ca ]; then export CARGO_HTTP_CAINFO=/run/secrets/xorder_ca; fi; \
    cargo build --locked --release -j "$MAGO_BUILD_JOBS" \
    && if [ "$MAGO_NATIVE_TESTS" = 1 ]; then \
         cargo test --locked -p mago --bin mago language_server::tests::external_analyzers -j "$MAGO_BUILD_JOBS"; \
       else test "$MAGO_NATIVE_TESTS" = 0; fi \
    && cp target/release/mago /mago \
    && sha256sum Cargo.lock > /mago-cargo-lock.sha256 \
    && sha256sum /candidate.patch > /mago-patch.sha256 \
    && git rev-parse HEAD > /mago-source.sha \
    && rustc --version > /mago-rust-version.txt

FROM ${BASE_IMAGE}
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
# Python 3.12 is isolated from Debian's /usr/bin/python3 (3.13).
COPY --from=python /usr/local /usr/local
COPY --from=uv /uv /usr/local/bin/uv
RUN ldconfig
RUN --mount=type=secret,id=xorder_ca \
    set -eu; \
    if [ -s /run/secrets/xorder_ca ]; then export CURL_CA_BUNDLE=/run/secrets/xorder_ca; fi; \
    curl --fail --location --retry 3 --silent --show-error \
      https://github.com/carthage-software/mago/releases/download/1.58.2/mago-1.58.2-x86_64-unknown-linux-gnu.tar.gz \
      --output /tmp/mago.tar.gz \
    && printf '%s\n' '80b6e6ed3cd2fe2da348f9cd83d23e638f2ccd44988d48bebd766c20ccd30dc2  /tmp/mago.tar.gz' > /tmp/mago.sha256 \
    && sha256sum --check --strict /tmp/mago.sha256 \
    && tar -xzf /tmp/mago.tar.gz -C /opt \
    && install -m 0755 /opt/mago-1.58.2-x86_64-unknown-linux-gnu/mago /usr/local/bin/mago-baseline \
    && mkdir -p /opt/licenses/mago \
    && cp /opt/mago-1.58.2-x86_64-unknown-linux-gnu/LICENSE-MIT /opt/mago-1.58.2-x86_64-unknown-linux-gnu/LICENSE-APACHE /opt/licenses/mago/ \
    && rm -rf /opt/mago-1.58.2-x86_64-unknown-linux-gnu /tmp/mago.tar.gz /tmp/mago.sha256
COPY --from=mago-build /mago /usr/local/bin/mago
COPY --from=mago-build /mago-patch.sha256 /mago-cargo-lock.sha256 /mago-source.sha /mago-rust-version.txt /opt/xorder/serena/
COPY images/php-mago-serena/serena/ /opt/xorder/serena/
COPY images/php-mago-serena/toolchain.lock.json images/php-mago-serena/identity.py /opt/xorder/serena/
COPY images/php-mago-serena/licenses/serena/ /opt/licenses/serena/
ENV UV_PYTHON_DOWNLOADS=never
RUN --mount=type=secret,id=xorder_ca \
    set -eu; \
    if [ -s /run/secrets/xorder_ca ]; then export SSL_CERT_FILE=/run/secrets/xorder_ca GIT_SSL_CAINFO=/run/secrets/xorder_ca; fi; \
    UV_PROJECT_ENVIRONMENT=/opt/venv uv --no-cache sync --project /opt/xorder/serena --frozen --no-dev --python /usr/local/bin/python3 \
    && /opt/venv/bin/python /opt/xorder/serena/patches/apply_serena.py > /opt/xorder/serena/serena-patch.json \
    && uv pip check --python /opt/venv/bin/python \
    && rm -rf /root/.cache/uv
COPY --chmod=755 images/php-mago-serena/entrypoint /opt/xorder/serena/entrypoint
ENV PATH=/opt/venv/bin:$PATH \
    SERENA_HOME=/home/dev/serena \
    DEV_IMAGE_IDENTITY=/opt/xorder/image-identity.json \
    MAGO_EXPERIMENTAL_SERVER=1 \
    PYTHONUNBUFFERED=1
RUN python /opt/xorder/serena/identity.py > /opt/xorder/image-identity.json \
    && mkdir -p /evidence /packages \
    && chown dev:dev /evidence /packages
WORKDIR /workspace
ENTRYPOINT ["bash", "/usr/local/bin/library-entrypoint", "/opt/xorder/serena/entrypoint"]
CMD ["bash"]
ARG SOURCE_COMMIT
ARG IMAGE_VERSION
LABEL org.opencontainers.image.source="https://github.com/xormania/xorder" \
      org.opencontainers.image.revision="${SOURCE_COMMIT}" \
      org.opencontainers.image.version="${IMAGE_VERSION}" \
      io.xorder.serena.revision="9e1cced0c34ed48d668e179f7c56c77b4d14a3e3" \
      io.xorder.mago.revision="46df50c96d93d0ac3655c116c375574277cf0b30"

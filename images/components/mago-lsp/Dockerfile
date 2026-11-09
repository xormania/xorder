# syntax=docker/dockerfile:1
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

FROM scratch
COPY --from=mago-build /mago /payload/bin/mago
COPY --from=mago-build /mago-patch.sha256 /mago-cargo-lock.sha256 /mago-source.sha /mago-rust-version.txt /payload/identity/

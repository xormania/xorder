# syntax=docker/dockerfile:1
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
ARG APT_REFRESH
COPY images/shared/install.sh /tmp/install-common
RUN test -n "$APT_REFRESH" && bash /tmp/install-common && rm /tmp/install-common \
    && rustup component add rustfmt clippy \
    && rustup target add wasm32-unknown-unknown
COPY images/shared/entrypoint.sh /usr/local/bin/library-entrypoint
ENV HOME=/home/dev CARGO_HOME=/home/dev/.cargo XDG_CACHE_HOME=/home/dev/.cache
WORKDIR /workspace
ENTRYPOINT ["bash", "/usr/local/bin/library-entrypoint"]
CMD ["bash"]
ARG SOURCE_COMMIT
ARG IMAGE_VERSION
LABEL org.opencontainers.image.source="https://github.com/xormania/xorder" \
      org.opencontainers.image.revision="${SOURCE_COMMIT}" \
      org.opencontainers.image.version="${IMAGE_VERSION}"

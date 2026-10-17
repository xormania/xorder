# syntax=docker/dockerfile:1
ARG UV_IMAGE
ARG BASE_IMAGE
FROM ${UV_IMAGE} AS uv
FROM ${BASE_IMAGE}
ARG APT_REFRESH
COPY images/shared/install.sh /tmp/install-common
RUN test -n "$APT_REFRESH" && bash /tmp/install-common && rm /tmp/install-common
COPY --from=uv /uv /uvx /usr/local/bin/
COPY images/shared/entrypoint.sh /usr/local/bin/library-entrypoint
COPY images/shared/uv-entrypoint.sh /usr/local/bin/library-uv-entrypoint
ENV HOME=/home/dev XDG_CACHE_HOME=/home/dev/.cache \
    UV_CACHE_DIR=/home/dev/.cache/uv UV_LINK_MODE=copy
WORKDIR /workspace
ENTRYPOINT ["bash", "/usr/local/bin/library-uv-entrypoint"]
CMD ["bash"]
ARG SOURCE_COMMIT
ARG IMAGE_VERSION
LABEL org.opencontainers.image.source="https://github.com/xormania/xorder" \
      org.opencontainers.image.revision="${SOURCE_COMMIT}" \
      org.opencontainers.image.version="${IMAGE_VERSION}"

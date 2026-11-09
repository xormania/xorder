# syntax=docker/dockerfile:1
ARG BASE_IMAGE
ARG MATRIX_IMAGE
FROM ${MATRIX_IMAGE} AS interpreters
FROM ${BASE_IMAGE}
ARG APT_REFRESH
RUN test -n "$APT_REFRESH" \
    && apt-get update && apt-get install -y --no-install-recommends tmux \
    && rm -rf /var/lib/apt/lists/*
COPY --from=interpreters /opt/xorder/python /opt/xorder/python
COPY --from=interpreters /opt/xorder/python-bin /opt/xorder/python-bin
COPY --from=interpreters /opt/xorder/python-matrix/versions.json /opt/xorder/python-matrix/versions.json
COPY --from=interpreters /opt/xorder/python-matrix/pip-bootstrap.json /opt/xorder/python-matrix/pip-bootstrap.json
ENV UV_PYTHON_INSTALL_DIR=/opt/xorder/python UV_PYTHON_DOWNLOADS=never \
    PATH=/opt/xorder/python-bin:${PATH}
ARG SOURCE_COMMIT
ARG IMAGE_VERSION
LABEL org.opencontainers.image.source="https://github.com/xormania/xorder" \
      org.opencontainers.image.revision="${SOURCE_COMMIT}" \
      org.opencontainers.image.version="${IMAGE_VERSION}"

# syntax=docker/dockerfile:1
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
ARG APT_REFRESH
COPY images/python-matrix/versions.json /opt/xorder/python-matrix/versions.json
COPY images/python-matrix/install.py /tmp/install-python-matrix.py
RUN test -n "$APT_REFRESH" \
    && apt-get update && apt-get install -y --no-install-recommends tmux \
    && rm -rf /var/lib/apt/lists/* \
    && python3 /tmp/install-python-matrix.py && rm /tmp/install-python-matrix.py
ENV UV_PYTHON_INSTALL_DIR=/opt/xorder/python UV_PYTHON_DOWNLOADS=never \
    PATH=/opt/xorder/python-bin:${PATH}
ARG SOURCE_COMMIT
ARG IMAGE_VERSION
LABEL org.opencontainers.image.source="https://github.com/xormania/xorder" \
      org.opencontainers.image.revision="${SOURCE_COMMIT}" \
      org.opencontainers.image.version="${IMAGE_VERSION}"

# syntax=docker/dockerfile:1
ARG UV_IMAGE
ARG BASE_IMAGE
FROM ${UV_IMAGE} AS uv
FROM ${BASE_IMAGE}
COPY --from=uv /uv /usr/local/bin/uv
COPY images/python-matrix/versions.json /opt/xorder/python-matrix/versions.json
COPY images/python-matrix/pip-bootstrap.json /opt/xorder/python-matrix/pip-bootstrap.json
COPY images/python-matrix/install.py scripts/fetch_build_input.py /tmp/python-matrix-build/
COPY scripts/xorder/download_cache.py scripts/xorder/transport.py /tmp/python-matrix-build/xorder/
RUN --mount=type=secret,id=xorder_ca \
    --mount=type=tmpfs,target=/run/xorder-build-trust \
    --mount=type=cache,id=xorder-python-matrix-downloads,target=/var/cache/xorder-downloads \
    python3 /tmp/python-matrix-build/install.py && rm -rf /tmp/python-matrix-build
COPY images/components/python-matrix-interpreters/verify.py /opt/xorder/components/python-matrix-interpreters/verify.py

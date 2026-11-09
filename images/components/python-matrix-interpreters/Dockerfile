# syntax=docker/dockerfile:1
ARG UV_IMAGE
ARG BASE_IMAGE
FROM ${UV_IMAGE} AS uv
FROM ${BASE_IMAGE}
COPY --from=uv /uv /usr/local/bin/uv
COPY images/python-matrix/versions.json /opt/xorder/python-matrix/versions.json
COPY images/python-matrix/install.py /tmp/install-python-matrix.py
RUN --mount=type=secret,id=xorder_ca \
    --mount=type=tmpfs,target=/run/xorder-build-trust \
    python3 /tmp/install-python-matrix.py && rm /tmp/install-python-matrix.py
COPY images/components/python-matrix-interpreters/verify.py /opt/xorder/components/python-matrix-interpreters/verify.py

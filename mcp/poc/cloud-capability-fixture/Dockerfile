# syntax=docker/dockerfile:1
# Accepted python-dev/3.14-trixie 1.1.4. This derivative is experimental.
FROM ghcr.io/xormania/python-dev@sha256:b232a236f5c74402be7488aab9e0c98bbb76a647e9667ac37e0cdb98553af589
WORKDIR /opt/xorder-cloud-probe
COPY requirements.lock ./
RUN --mount=type=secret,id=xorder_ca \
    --mount=type=tmpfs,target=/run/xorder-build-trust \
    if [ -f /run/secrets/xorder_ca ]; then \
      cat /etc/ssl/certs/ca-certificates.crt /run/secrets/xorder_ca > /run/xorder-build-trust/ca.pem; \
      export PIP_CERT=/run/xorder-build-trust/ca.pem; \
    fi \
    && python3 -m venv /opt/xorder-cloud-probe/venv \
    && /opt/xorder-cloud-probe/venv/bin/python -m pip install \
       --no-cache-dir --require-hashes --only-binary=:all: -r requirements.lock
COPY probe.py smoke.py packet.md manifest.json ./
COPY xorder-cloud-probe /usr/local/bin/xorder-cloud-probe
RUN chmod 0755 /usr/local/bin/xorder-cloud-probe
ARG SOURCE_COMMIT=unrecorded
ENV XORDER_PROBE_SOURCE=${SOURCE_COMMIT} PYTHONDONTWRITEBYTECODE=1
LABEL org.opencontainers.image.source="https://github.com/xormania/xorder" \
      org.opencontainers.image.revision="${SOURCE_COMMIT}" \
      org.opencontainers.image.version="0.1.0-poc" \
      org.opencontainers.image.description="Experimental cloud capability fixture"
WORKDIR /workspace
EXPOSE 8000
# Preserve xorder's CA, HOME and PUID/PGID entrypoint contract.
CMD ["xorder-cloud-probe", "serve", "--transport", "http", "--host", "0.0.0.0"]

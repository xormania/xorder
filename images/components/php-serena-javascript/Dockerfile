# syntax=docker/dockerfile:1.7
ARG NODE_IMAGE
FROM ${NODE_IMAGE}
COPY images/php-serena/package*.json /opt/xorder/serena/javascript/
RUN --mount=type=secret,id=xorder_ca \
    set -eu; \
    if [ -s /run/secrets/xorder_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/xorder_ca; fi; \
    npm ci --prefix /opt/xorder/serena/javascript --ignore-scripts --no-audit --no-fund \
    && npm cache clean --force

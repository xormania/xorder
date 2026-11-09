# syntax=docker/dockerfile:1.7
ARG NODE_IMAGE
FROM ${NODE_IMAGE}
ENV CHROME_DEVTOOLS_MCP_NO_USAGE_STATISTICS=1 \
    CHROME_DEVTOOLS_MCP_NO_UPDATE_CHECKS=1
COPY images/php-chrome-dev/package.json images/php-chrome-dev/package-lock.json /opt/xorder/chrome-devtools/
RUN --mount=type=secret,id=xorder_ca \
    set -eu; \
    if [ -s /run/secrets/xorder_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/xorder_ca; fi; \
    npm ci --prefix /opt/xorder/chrome-devtools --omit=dev --ignore-scripts --no-audit --no-fund \
    && npm cache clean --force

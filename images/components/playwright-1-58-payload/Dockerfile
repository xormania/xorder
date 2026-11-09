# syntax=docker/dockerfile:1.7
ARG NODE_IMAGE
FROM ${NODE_IMAGE}
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright-browsers
COPY images/playwright-browser/lines/1.58-trixie/package.json images/playwright-browser/lines/1.58-trixie/package-lock.json /opt/playwright/
# Download the npm closure and every engine once. OS packages and rendering
# configuration belong to the final runtime, so apt refreshes reuse this payload.
RUN --mount=type=secret,id=xorder_ca \
    set -eu; \
    if [ -s /run/secrets/xorder_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/xorder_ca; fi; \
    npm ci --prefix /opt/playwright --ignore-scripts --no-audit --no-fund \
    && /opt/playwright/node_modules/.bin/playwright install chromium firefox webkit \
    && chmod -R a+rX /opt/playwright-browsers \
    && rm -rf /root/.npm

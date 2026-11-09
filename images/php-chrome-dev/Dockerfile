# syntax=docker/dockerfile:1.7
ARG BASE_IMAGE
ARG NODE_IMAGE
ARG CHROME_IMAGE
ARG MCP_IMAGE
FROM ${NODE_IMAGE} AS node
FROM ${CHROME_IMAGE} AS chrome
FROM ${MCP_IMAGE} AS mcp
FROM ${BASE_IMAGE}

COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
COPY --from=chrome /opt/chrome-linux64 /opt/chrome-linux64
COPY --from=chrome /opt/chrome-version /opt/chrome-version
COPY --from=chrome /opt/xorder/components/chrome-for-testing-157.lock.json /opt/xorder/components/chrome-for-testing-157.lock.json
COPY --from=mcp /opt/xorder/chrome-devtools /opt/xorder/chrome-devtools
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && ln -s /opt/xorder/chrome-devtools/node_modules/chrome-devtools-mcp /usr/local/lib/node_modules/chrome-devtools-mcp \
    && ln -s /opt/xorder/chrome-devtools/node_modules/.bin/chrome-devtools-mcp /usr/local/bin/chrome-devtools-mcp \
    && ln -s /opt/chrome-linux64/chrome /usr/local/bin/chrome

COPY images/php-chrome-dev/toolchain.lock.json /opt/xorder/chrome-composition.lock.json
COPY images/php-chrome-dev/compose-lock.py /opt/xorder/compose-chrome-lock.py
ENV CHROME_PATH=/usr/local/bin/chrome \
    CHROME_DEVTOOLS_MCP_NO_USAGE_STATISTICS=1 \
    CHROME_DEVTOOLS_MCP_NO_UPDATE_CHECKS=1

# Final assembly executes no browser or npm download. Expand the independently
# owned component pins, then re-measure the full inherited toolchain as before.
RUN python /opt/xorder/compose-chrome-lock.py > /opt/xorder/chrome-toolchain.lock.json \
    && python /opt/xorder/serena/identity.py > /opt/xorder/image-identity.json

ARG SOURCE_COMMIT
ARG IMAGE_VERSION
LABEL org.opencontainers.image.source="https://github.com/xormania/xorder" \
      org.opencontainers.image.revision="${SOURCE_COMMIT}" \
      org.opencontainers.image.version="${IMAGE_VERSION}"

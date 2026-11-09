# syntax=docker/dockerfile:1.7
ARG BASE_IMAGE
# Deliberately retain the consumer's qualified Node input independently of the
# shared tools.json refresh cadence. Update this and toolchain.lock.json together.
FROM docker.io/library/node:22-trixie@sha256:77d0c7953e80648137a237496c8edbcb3a14bedc5c5298b93a6d0dfa6c3e1271 AS node
FROM ${BASE_IMAGE}

COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

COPY images/php-chrome-dev/toolchain.lock.json /opt/xorder/chrome-toolchain.lock.json
# Debian Chromium and chromedriver remain inherited for Panther. Chrome for
# Testing is the explicitly owned browser supported by Chrome DevTools MCP.
RUN --mount=type=secret,id=xorder_ca \
    set -eu; \
    if [ -s /run/secrets/xorder_ca ]; then export CURL_CA_BUNDLE=/run/secrets/xorder_ca; fi; \
    chrome_url="$(python3 -c 'import json; print(json.load(open("/opt/xorder/chrome-toolchain.lock.json"))["browser"]["url"])')"; \
    curl --fail --location --retry 3 --output /tmp/chrome.zip "$chrome_url" \
    && python3 -c 'import hashlib, json, sys; expected = json.load(open("/opt/xorder/chrome-toolchain.lock.json"))["browser"]["archive_sha256"]; actual = hashlib.file_digest(open("/tmp/chrome.zip", "rb"), "sha256").hexdigest(); sys.exit(0 if actual == expected else "Chrome for Testing archive SHA-256 mismatch")' \
    && unzip -q /tmp/chrome.zip -d /opt \
    && rm /tmp/chrome.zip \
    && ln -s /opt/chrome-linux64/chrome /usr/local/bin/chrome \
    && python3 -c 'import json; print(json.load(open("/opt/xorder/chrome-toolchain.lock.json"))["browser"]["chrome_for_testing"])' > /opt/chrome-version

# npm ci verifies the exact registry tarball integrity retained in package-lock.
# No install scripts or optional peer integrations are needed by this MCP server.
COPY images/php-chrome-dev/package.json images/php-chrome-dev/package-lock.json /opt/xorder/chrome-devtools/
RUN --mount=type=secret,id=xorder_ca \
    set -eu; \
    if [ -s /run/secrets/xorder_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/xorder_ca; fi; \
    npm ci --prefix /opt/xorder/chrome-devtools --omit=dev --ignore-scripts --no-audit --no-fund \
    && ln -s /opt/xorder/chrome-devtools/node_modules/chrome-devtools-mcp /usr/local/lib/node_modules/chrome-devtools-mcp \
    && ln -s /opt/xorder/chrome-devtools/node_modules/.bin/chrome-devtools-mcp /usr/local/bin/chrome-devtools-mcp \
    && npm cache clean --force

ENV CHROME_PATH=/usr/local/bin/chrome \
    CHROME_DEVTOOLS_MCP_NO_USAGE_STATISTICS=1 \
    CHROME_DEVTOOLS_MCP_NO_UPDATE_CHECKS=1

# Re-measure all inherited tools and the newly installed browser in one record.
# Keep the parent's library-entrypoint -> Serena seed hook and default bash CMD.
RUN python /opt/xorder/serena/identity.py > /opt/xorder/image-identity.json

ARG SOURCE_COMMIT
ARG IMAGE_VERSION
LABEL org.opencontainers.image.source="https://github.com/xormania/xorder" \
      org.opencontainers.image.revision="${SOURCE_COMMIT}" \
      org.opencontainers.image.version="${IMAGE_VERSION}"

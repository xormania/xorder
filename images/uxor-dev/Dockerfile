# syntax=docker/dockerfile:1
ARG NODE_IMAGE
ARG BASE_IMAGE
FROM ${NODE_IMAGE} AS node
FROM ${BASE_IMAGE}
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx
ARG TAILWIND_VERSION
ARG TAILWIND_URL
ARG TAILWIND_SHA256
RUN mkdir -p /opt/tailwind \
    && curl --fail --location --retry 3 "${TAILWIND_URL}" -o /opt/tailwind/tailwindcss-linux-x64 \
    && echo "${TAILWIND_SHA256}  /opt/tailwind/tailwindcss-linux-x64" | sha256sum --check --strict \
    && chmod 755 /opt/tailwind/tailwindcss-linux-x64 \
    && printf '%s\n' "${TAILWIND_VERSION}" > /opt/tailwind/version \
    && ln -s /opt/tailwind/tailwindcss-linux-x64 /usr/local/bin/tailwindcss
COPY images/uxor-dev/entrypoint.sh /usr/local/bin/uxor-entrypoint
COPY images/uxor-dev/prime-tailwind.sh /usr/local/bin/uxor-prime-tailwind
ARG SOURCE_COMMIT
ARG IMAGE_VERSION
LABEL org.opencontainers.image.revision="${SOURCE_COMMIT}" \
      org.opencontainers.image.version="${IMAGE_VERSION}"

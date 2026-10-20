# syntax=docker/dockerfile:1
ARG NODE_IMAGE
ARG BASE_IMAGE
FROM ${NODE_IMAGE} AS node
FROM ${BASE_IMAGE}
ARG APT_REFRESH
COPY images/shared/install.sh /tmp/install-common
RUN test -n "$APT_REFRESH" && bash /tmp/install-common \
    && apt-get update && apt-get install -y --no-install-recommends tmux gpgv \
    && rm -rf /var/lib/apt/lists/* /tmp/install-common
RUN chown -R 0:0 /home/dev
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx
COPY images/shared/entrypoint.sh /usr/local/bin/library-entrypoint
COPY images/harness-live/entrypoint.sh /usr/local/bin/harness-entrypoint
COPY images/harness-live/session.sh /usr/local/bin/harness-session
COPY images/harness-live/harnesses.py /usr/local/bin/harnesses
COPY images/harness-live/harness-pins.json /usr/local/share/xorder/harness-pins.json
COPY images/harness-live/root_trust.py /usr/local/share/xorder/root_trust.py
COPY images/harness-live/provenance.py /usr/local/share/xorder/provenance.py
COPY images/harness-live/trust /usr/local/share/xorder/trust
RUN chmod 0755 /usr/local/bin/harnesses
ENV HOME=/home/dev XDG_CACHE_HOME=/home/dev/.cache \
    HARNESS_ROOT=/home/dev/.local/share/xorder/harnesses \
    HARNESS_PINS=/usr/local/share/xorder/harness-pins.json \
    HARNESS_AUTO_INSTALL=1 \
    DISABLE_AUTOUPDATER=1 DISABLE_UPDATES=1 GROK_DISABLE_AUTOUPDATER=1
WORKDIR /workspace
ENTRYPOINT ["bash", "/usr/local/bin/harness-entrypoint"]
CMD ["bash"]
ARG SOURCE_COMMIT
ARG IMAGE_VERSION
LABEL org.opencontainers.image.source="https://github.com/xormania/xorder" \
      org.opencontainers.image.revision="${SOURCE_COMMIT}" \
      org.opencontainers.image.version="${IMAGE_VERSION}"

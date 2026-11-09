# syntax=docker/dockerfile:1
ARG BASE_IMAGE
ARG SERENA_JAVASCRIPT_IMAGE
ARG SERENA_PYTHON_IMAGE
ARG PHPACTOR_IMAGE
FROM ${SERENA_PYTHON_IMAGE} AS serena-python
FROM ${PHPACTOR_IMAGE} AS phpactor
FROM ${SERENA_JAVASCRIPT_IMAGE} AS javascript
FROM ${BASE_IMAGE}
# Both donors use the exact matching php-native-85 foundation: Debian Python's
# interpreter path, shared libraries and venv shebangs remain compatible.
COPY --from=serena-python /usr/local/bin/uv /usr/local/bin/uv
COPY --from=serena-python /opt/serena-source /opt/serena-source
COPY --from=serena-python /opt/serena-env /opt/serena-env
COPY --from=serena-python /opt/xorder/serena /opt/xorder/serena

# Node/npm changes have no edge into the retained Python dependency component.
COPY --from=javascript /usr/local/bin/node /usr/local/bin/node
COPY --from=javascript /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm
COPY --from=javascript /opt/xorder/serena/javascript /opt/xorder/serena/javascript
COPY --from=phpactor /payload/phpactor.phar /opt/xorder/serena/phpactor.phar
COPY --chmod=755 images/php-serena/launch.py /usr/local/bin/library-serena
COPY images/php-serena/integration.py /usr/local/bin/integration.py
COPY images/shared/uv-entrypoint.sh /usr/local/bin/library-uv-entrypoint
ENV PYTHONDONTWRITEBYTECODE=1
ENTRYPOINT ["bash", "/usr/local/bin/library-uv-entrypoint"]
CMD ["library-serena"]

ARG SOURCE_COMMIT
ARG IMAGE_VERSION
LABEL org.opencontainers.image.source="https://github.com/xormania/xorder" \
      org.opencontainers.image.revision="${SOURCE_COMMIT}" \
      org.opencontainers.image.version="${IMAGE_VERSION}" \
      io.xorder.serena.revision="b79e2a55f9d4072084977dd35bd07d31146d88b9"

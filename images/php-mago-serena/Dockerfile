# syntax=docker/dockerfile:1
ARG BASE_IMAGE
ARG MAGO_IMAGE
ARG MAGO_BASELINE_IMAGE
ARG NATIVE_MAGO_IMAGE
ARG SERENA_IMAGE
FROM ${MAGO_IMAGE} AS mago
FROM ${MAGO_BASELINE_IMAGE} AS baseline
FROM ${NATIVE_MAGO_IMAGE} AS native
FROM ${SERENA_IMAGE} AS serena
FROM ${BASE_IMAGE}
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
# Prepared payloads are independently keyed and reusable across PHP/browser lines.
COPY --from=serena /payload/python/ /usr/local/
COPY --from=serena /payload/venv/ /opt/venv/
COPY --from=mago /payload/bin/mago /usr/local/bin/mago
COPY --from=mago /payload/identity/ /opt/xorder/serena/
COPY --from=baseline /payload/bin/mago /usr/local/bin/mago-baseline
COPY --from=baseline /payload/licenses/ /opt/licenses/mago/
COPY --from=native /payload/bin/mago /usr/local/bin/mago-native
COPY --from=native /payload/licenses/ /opt/licenses/mago-native/
RUN ldconfig
# This cheap overlay installs only the adapter; dependency sync is in serena-deps.
COPY images/php-mago-serena/serena/pyproject.toml images/php-mago-serena/serena/uv.lock /opt/xorder/serena/
COPY images/php-mago-serena/serena/adapter/ /opt/xorder/serena/adapter/
ENV UV_PYTHON_DOWNLOADS=never
RUN --mount=type=secret,id=xorder_ca \
    set -eu; \
    if [ -s /run/secrets/xorder_ca ]; then export SSL_CERT_FILE=/run/secrets/xorder_ca GIT_SSL_CAINFO=/run/secrets/xorder_ca; fi; \
    UV_PROJECT_ENVIRONMENT=/opt/venv uv --no-cache sync --project /opt/xorder/serena --frozen --no-dev --no-editable --inexact --offline --no-build-isolation --python /usr/local/bin/python3 \
    && uv pip check --python /opt/venv/bin/python \
    && rm -rf /root/.cache/uv
COPY images/php-mago-serena/serena/patches/ /opt/xorder/serena/patches/
RUN /opt/venv/bin/python /opt/xorder/serena/patches/apply_serena.py > /opt/xorder/serena/serena-patch.json
COPY images/php-mago-serena/serena/config/ /opt/xorder/serena/config/
COPY images/php-mago-serena/toolchain.lock.json images/php-mago-serena/identity.py /opt/xorder/serena/
COPY images/php-mago-serena/licenses/serena/ /opt/licenses/serena/
COPY images/php-mago-serena/symfony/ /opt/xorder/symfony/
COPY --chmod=755 images/php-mago-serena/entrypoint /opt/xorder/serena/entrypoint
RUN chmod 0755 /opt/xorder/symfony/project.py \
    && ln -s /opt/xorder/symfony/project.py /usr/local/bin/library-symfony-mago
ENV PATH=/opt/venv/bin:$PATH \
    SERENA_HOME=/home/dev/serena \
    DEV_IMAGE_IDENTITY=/opt/xorder/image-identity.json \
    MAGO_EXPERIMENTAL_SERVER=1 \
    PYTHONUNBUFFERED=1
RUN python /opt/xorder/serena/identity.py > /opt/xorder/image-identity.json \
    && mkdir -p /evidence /packages \
    && chown dev:dev /evidence /packages
WORKDIR /workspace
ENTRYPOINT ["bash", "/usr/local/bin/library-entrypoint", "/opt/xorder/serena/entrypoint"]
CMD ["bash"]
ARG SOURCE_COMMIT
ARG IMAGE_VERSION
LABEL org.opencontainers.image.source="https://github.com/xormania/xorder" \
      org.opencontainers.image.revision="${SOURCE_COMMIT}" \
      org.opencontainers.image.version="${IMAGE_VERSION}" \
      io.xorder.serena.revision="ede329aaf0c824bea75455a2926f01420d7aa620" \
      io.xorder.mago.revision="46df50c96d93d0ac3655c116c375574277cf0b30" \
      io.xorder.mago.native.version="1.59.0"

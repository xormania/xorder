# syntax=docker/dockerfile:1.7
ARG PHP_EXTENSIONS_IMAGE
ARG PHP_TOOLS_IMAGE
ARG PHP_DOWNLOADS_IMAGE
FROM ${PHP_TOOLS_IMAGE} AS php-tools
FROM ${PHP_DOWNLOADS_IMAGE} AS php-downloads
FROM ${PHP_EXTENSIONS_IMAGE}
COPY --from=php-tools /usr/local/bin/composer /usr/local/bin/composer
COPY --from=php-downloads /payload/symfony /usr/local/bin/symfony
COPY --from=php-downloads /payload/infection /opt/xorder/infection
# Portable payloads retain every ABI. Select on the final runtime, so an 8.4
# tooling builder cannot accidentally remove the 8.5 Turbo implementation.
# Copy and filter in one layer; a COPY before pruning would retain discarded bytes.
COPY images/shared/package-phpstan.py /tmp/package-phpstan.py
RUN --mount=type=bind,from=php-tools,source=/opt/xorder/php-tools,target=/prepared/php-tools,readonly \
    mkdir -p /opt/xorder/php-tools \
    && cp -a /prepared/php-tools/. /opt/xorder/php-tools/ \
    && composer check-platform-reqs --working-dir=/opt/xorder/php-tools \
    && python3 /tmp/package-phpstan.py /opt/xorder/php-tools \
    && php /opt/xorder/infection/infection.phar --version \
    && rm /tmp/package-phpstan.py
COPY --chmod=755 images/shared/infection.sh /usr/local/bin/infection
COPY images/shared/development.ini /usr/local/etc/php/conf.d/zz-development.ini
COPY --chmod=755 images/shared/php-coverage.py /usr/local/bin/library-php-coverage
COPY --chmod=755 images/shared/php-tests.py /usr/local/bin/library-php-tests
COPY images/shared/entrypoint.sh /usr/local/bin/library-entrypoint
ENV HOME=/home/dev COMPOSER_HOME=/home/dev/.composer \
    XDG_CACHE_HOME=/home/dev/.cache XDEBUG_MODE=off
WORKDIR /workspace
ENTRYPOINT ["bash", "/usr/local/bin/library-entrypoint"]
CMD ["bash"]
ARG SOURCE_COMMIT
ARG IMAGE_VERSION
LABEL org.opencontainers.image.source="https://github.com/xormania/xorder" \
      org.opencontainers.image.revision="${SOURCE_COMMIT}" \
      org.opencontainers.image.version="${IMAGE_VERSION}"

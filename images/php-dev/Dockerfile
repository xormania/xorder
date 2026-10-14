# syntax=docker/dockerfile:1
ARG COMPOSER_IMAGE
ARG BASE_IMAGE
FROM ${COMPOSER_IMAGE} AS composer
FROM ${BASE_IMAGE}
ARG APT_REFRESH
COPY images/shared/install.sh /tmp/install-common
RUN test -n "$APT_REFRESH" && bash /tmp/install-common && rm /tmp/install-common
ARG REDIS_VERSION
ARG XDEBUG_VERSION
ARG PCOV_VERSION
COPY images/shared/install-php.sh /tmp/install-php
RUN bash /tmp/install-php && rm /tmp/install-php
COPY --from=composer /usr/bin/composer /usr/local/bin/composer
COPY images/shared/php-tools-composer.json /opt/xorder/php-tools/composer.json
COPY images/shared/php-tools-composer.lock /opt/xorder/php-tools/composer.lock
COPY images/shared/package-phpstan.py /tmp/package-phpstan.py
RUN COMPOSER_ALLOW_SUPERUSER=1 composer install --working-dir=/opt/xorder/php-tools \
    --no-interaction --no-progress --prefer-dist --no-scripts --no-plugins --no-cache \
    && composer check-platform-reqs --working-dir=/opt/xorder/php-tools \
    && python3 /tmp/package-phpstan.py /opt/xorder/php-tools \
    && rm /tmp/package-phpstan.py
ARG SYMFONY_URL
ARG SYMFONY_SHA256
COPY images/shared/install-symfony.sh /tmp/install-symfony
RUN bash /tmp/install-symfony && rm /tmp/install-symfony
ARG INFECTION_URL
ARG INFECTION_SHA256
COPY images/shared/install-infection.sh /tmp/install-infection
RUN bash /tmp/install-infection && rm /tmp/install-infection
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

# syntax=docker/dockerfile:1.7
ARG COMPOSER_IMAGE
ARG PHP_FOUNDATION_IMAGE
FROM ${COMPOSER_IMAGE} AS composer
FROM ${PHP_FOUNDATION_IMAGE}
COPY --from=composer /usr/bin/composer /usr/local/bin/composer
# Retain the complete upstream native bundle here. The consuming PHP CLI ABI
# selects its own PHPStan Turbo binary when php-dev is composed.
COPY images/shared/php-tools-composer.json images/shared/php-tools-composer.lock /opt/xorder/php-tools/
RUN --mount=type=secret,id=xorder_ca \
    set -eu; \
    if [ -s /run/secrets/xorder_ca ]; then export COMPOSER_CAFILE=/run/secrets/xorder_ca; fi; \
    sha256sum /opt/xorder/php-tools/composer.json /opt/xorder/php-tools/composer.lock > /tmp/php-tools-inputs.sha256 \
    && COMPOSER_ALLOW_SUPERUSER=1 composer install --working-dir=/opt/xorder/php-tools \
      --no-interaction --no-progress --prefer-dist --no-scripts --no-plugins --no-cache \
    && composer check-platform-reqs --working-dir=/opt/xorder/php-tools \
    && sha256sum --check /tmp/php-tools-inputs.sha256 \
    && rm /tmp/php-tools-inputs.sha256

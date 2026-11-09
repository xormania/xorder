# syntax=docker/dockerfile:1
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
ARG APT_REFRESH
ARG REDIS_VERSION
ARG XDEBUG_VERSION
ARG PCOV_VERSION
COPY images/shared/install-php.sh /tmp/install-php
RUN test -n "$APT_REFRESH" && bash /tmp/install-php && rm /tmp/install-php

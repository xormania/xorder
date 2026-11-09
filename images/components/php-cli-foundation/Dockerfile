# syntax=docker/dockerfile:1
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
ARG APT_REFRESH
# Keep the established PHP CLI workstation contract in a reusable foundation.
# Native PHP extensions and portable development tools have separate inputs.
COPY images/shared/install.sh /tmp/install-common
RUN test -n "$APT_REFRESH" && bash /tmp/install-common && rm /tmp/install-common

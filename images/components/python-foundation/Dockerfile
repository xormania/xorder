# syntax=docker/dockerfile:1
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
ARG APT_REFRESH
COPY images/shared/install.sh /tmp/install-common
RUN test -n "$APT_REFRESH" && bash /tmp/install-common && rm /tmp/install-common
COPY images/shared/entrypoint.sh /usr/local/bin/library-entrypoint
ENV HOME=/home/dev XDG_CACHE_HOME=/home/dev/.cache
WORKDIR /workspace
ENTRYPOINT ["bash", "/usr/local/bin/library-entrypoint"]
CMD ["bash"]
COPY images/components/python-foundation/verify.py /opt/xorder/components/python-foundation/verify.py
COPY images/components/python-foundation/verify_upstream.py /opt/xorder/components/python-foundation/verify_upstream.py
ARG BASE_IMAGE
RUN printf '%s\n' "$BASE_IMAGE" > /opt/xorder/components/python-foundation/upstream-image

# syntax=docker/dockerfile:1.7
ARG PYTHON_IMAGE
FROM ${PYTHON_IMAGE}
COPY scripts/fetch_build_input.py /opt/xorder/tools/
COPY scripts/xorder/download_cache.py scripts/xorder/transport.py /opt/xorder/tools/xorder/
COPY images/components/chrome-for-testing-157/toolchain.lock.json /opt/xorder/components/chrome-for-testing-157.lock.json
COPY images/components/chrome-for-testing-157/extract.py /opt/xorder/tools/extract-chrome.py
RUN --mount=type=secret,id=xorder_ca \
    --mount=type=cache,target=/root/.cache/xorder/build-downloads \
    set -eu; \
    if [ -s /run/secrets/xorder_ca ]; then export SSL_CERT_FILE=/run/secrets/xorder_ca; fi; \
    chrome_url="$(python3 -c 'import json; print(json.load(open("/opt/xorder/components/chrome-for-testing-157.lock.json"))["browser"]["url"])')"; \
    chrome_sha="$(python3 -c 'import json; print(json.load(open("/opt/xorder/components/chrome-for-testing-157.lock.json"))["browser"]["archive_sha256"])')"; \
    python3 /opt/xorder/tools/fetch_build_input.py --url "$chrome_url" --sha256 "$chrome_sha" --destination /tmp/chrome.zip \
    && python3 /opt/xorder/tools/extract-chrome.py /tmp/chrome.zip /opt \
    && rm /tmp/chrome.zip \
    && python3 -c 'import json; print(json.load(open("/opt/xorder/components/chrome-for-testing-157.lock.json"))["browser"]["chrome_for_testing"])' > /opt/chrome-version

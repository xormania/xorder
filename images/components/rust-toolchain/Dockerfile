# syntax=docker/dockerfile:1
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
# These compiler capabilities depend on Rust, not on xorder's Debian package feed.
RUN rustup component add rustfmt clippy \
    && rustup target add wasm32-unknown-unknown \
    && cargo fmt --version && cargo clippy --version \
    && rustup target list --installed > /tmp/rust-targets \
    && grep -Fx wasm32-unknown-unknown /tmp/rust-targets && rm /tmp/rust-targets

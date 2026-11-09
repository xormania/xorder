# Verified build downloads

Pinned build tools use a shared SHA-256 cache independently of Docker layer
ancestry. `scripts/xorder/download_cache.py` reuses the existing HTTPS transfer
and atomic checksum verification in `xorder.transport`. Every cache hit is
rehashed before use; a corrupt entry is fetched again and never accepted as a
successful hit. Parallel Linux consumers of the same digest acquire it once.
Transient network failures receive bounded retries; checksum failures and
permanent HTTP errors do not.

The default location is `$XDG_CACHE_HOME/xorder/build-downloads/sha256`, with
`~/.cache` as the XDG fallback. `XORDER_DOWNLOAD_CACHE` selects an explicit
directory for CI or a build cache mount. This is separate from application
installation and rollback blobs. Deleting this build cache must not remove
application recovery data.

Materialize an input with:

```sh
python3 scripts/fetch_build_input.py --url "$PINNED_URL" \
  --sha256 "$EXPECTED_SHA256" --destination /tmp/tool.archive
```

A Docker stage can copy `scripts/fetch_build_input.py` into a tools directory
and `scripts/xorder/download_cache.py` plus `scripts/xorder/transport.py` into
its `xorder/` subdirectory. Python's namespace package imports need no extra
dependencies. Include those files and the selected URL/hash in the component's
build identity.

The fast-check workflow restores its verified binary downloads before setup.
Trusted master pushes save newly acquired downloads immediately after setup,
so a later lint failure does not discard them. Checksum verification still
runs after restore. The scanner and signer installers use the same primitive;
publication workflows can persist their selected cache directory separately.

The Cosign 3.1.3 Linux/amd64 pin is the release asset digest reported by
the [upstream release](https://github.com/sigstore/cosign/releases/tag/v3.1.3).
This changes acquisition reuse, not image-signing or verification policy.

A local cache mount alone does not demonstrate availability on a fresh runner.
Build automation must restore the cache or retrieve a retained prepared
component. Public release availability checks deliberately keep using a fresh
transfer: cached bytes cannot prove that a published URL currently works.

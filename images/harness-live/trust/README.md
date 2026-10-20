# Harness release verification keys

These reviewed public keys are image inputs. Runtime downloads do not replace
them or add trust keys from an operator's HOME.

- `claude-code.asc` is Anthropic's Claude Code release signing key, published at
  <https://downloads.claude.ai/keys/claude-code.asc>. Its primary fingerprint is
  `31DDDE24DDFAB679F42D7BD2BAA929FF1A7ECACE`, as published in the
  [official verification instructions](https://code.claude.com/docs/en/setup#binary-integrity-and-code-signing).
  The manager verifies the exact version's detached `manifest.json.sig`, then
  checks the native binary against that signed manifest before executing it.
- `npm-registry.pem` is the active ECDSA registry signing public key from
  <https://registry.npmjs.org/-/npm/v1/keys>, with registry key ID
  `SHA256:DhQ8wR5APBvFHLF/+Tc+AYvPOdTpcIDqOhxsBHRwC7U`. This is the registry's
  identifier; it is not a SHA256 digest of the PEM or SPKI DER file.
  [npm documents](https://docs.npmjs.com/about-registry-signatures/) the signed
  message as `name@version:dist.integrity`. The manager verifies the exact Grok
  platform package's signature, then its SHA512 tarball identity. It reads only
  the named regular binary payload and decompresses it with image-owned Node.

The Grok npm distribution is an
[official alternative](https://docs.x.ai/build/enterprise) to its shell installer.
Neither mutable vendor shell installer is downloaded or executed. Future exact
releases and explicit latest-version updates work when signed by these trusted
keys. Key rotation requires a reviewed xorder update; an unrecognized key fails
verification before vendor code runs. Signatures establish release identity,
not a claim that publisher code cannot contain defects.

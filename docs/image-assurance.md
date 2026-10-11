# Image assurance and consumer verification

New image publication scans and signs the **published digest** before exact-tag
promotion. Scans and SBOM generation retrieve that digest anonymously, using an
explicit empty registry credential configuration. Image recipes and revisions do not change merely because the
publication workflow gains assurance. Historical release records retain their
original evidence; absence of `assurance` means no assurance claim is recorded.
A signature establishes who signed those bytes. It does not establish that an
image has no vulnerabilities or that its behavior is correct.

## Evidence and gate

Each newly assured digest has:

- A Trivy JSON vulnerability report covering the Linux amd64 image's OS and
  recognized application packages. Unrecognized software and scanner blind spots
  remain limitations.
- A CycloneDX SBOM and the scanner's version/database observation.
- A keyless cosign image signature, a signed SBOM attestation, and a signed
  xorder receipt attestation binding the exact image digest, original image
  source commit, scan policy, timestamp, and SHA-256 of each evidence file.
- Public GitHub Release assets containing `assurance.json` and the
  content-addressed scan, SBOM, and scanner/database JSON files. Workflow
  artifacts also retain failed scans for diagnosis; they have retention limits.

Policy `no-fixable-critical-v1` blocks publication when Trivy reports a CRITICAL
finding with a known fixed version. HIGH findings, and CRITICAL findings with no
reported fix, remain visible in the report and receipt counts. A passed gate
therefore means that specific policy passed at the observed database state.
It is not a clean bill of health. No ignore list or silent exception is applied.
The scanner receives empty configuration and ignore files and no inherited
`TRIVY_*` options, preventing local settings from suppressing findings.
Scanner failures, unsupported/missing OS results, incomplete SBOMs, and failed
signature or attestation checks stop publication.

Signing uses GitHub OIDC only in publisher jobs on master. The trusted
certificate identity is exactly:

```text
https://github.com/xormania/xorder/.github/workflows/publish.yml@refs/heads/master
```

The issuer is `https://token.actions.githubusercontent.com`. Consumer checks do
not accept arbitrary identities from an uploaded receipt. They check the signed
predicate and subject digest, compare every evidence checksum, and reapply the
recorded scan policy. No transparency-log or digest-claim checks are disabled.
The browser parity job remains a separate runner with no publication token,
registry login, or checkout credentials; signing does not run consumer code.

## Verify a newly assured release

Install cosign 3.1.3 through the pinned official installer (or an independently
verified installation), clone the repository, and choose an exact accepted
release record. The command performs anonymous public downloads and registry
verification even if a publisher's credentials exist in its environment:

```sh
python3 scripts/image_assurance.py verify \
  release-records/FAMILY/LINE/VERSION.json --output /tmp/xorder-evidence
```

Use the verified record's `publication.repository@publication.digest` when
starting containers. Existing records without an assurance field fail this
particular command with an explicit explanation; they remain selectable under
their original behavior verification contract. Consumers decide when to upgrade
pins or require assurance. `catalog-evidence` requires complete assurance and
verifies public evidence and signatures for every newly added image record
relative to the PR's trusted base commit. Existing records keep their original
contracts; lifecycle edits cannot change their immutable evidence.
Manual full-ledger checks use `python3 scripts/catalog_checks.py --audit` and
allow historical unsigned records. That audit is distinct from an additions
acceptance gate; PR checks require a valid ancestral `--base` and cannot use
audit mode. Hosted manual audits require the master ref, so an audit on a PR's
feature ref cannot satisfy its `catalog-evidence` acceptance context.

The equivalent image-signature check is:

```sh
cosign verify \
  --certificate-identity https://github.com/xormania/xorder/.github/workflows/publish.yml@refs/heads/master \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  ghcr.io/xormania/IMAGE@sha256:DIGEST
```

This checks the image signature alone. Use the helper to verify the exact
receipt, SBOM, vulnerability observations, and policy as well.

## Observe assurance for an existing digest

A master push that changes `publish.yml`, `scripts/image_assurance.py`, or
`scripts/release.py` runs this assurance path against the latest accepted
`python-dev/3.14-trixie` digest. This small scoped smoke exercises real scanning,
SBOM generation, OIDC signing and anonymous verification without rebuilding an
image. Unrelated pushes do not scan it again. The public separate evidence
Release and workflow output establish what actually succeeded.

`Publish verified resources` also supports an optional `assurance_record` manual
input. Supply an existing accepted `release-records/FAMILY/LINE/VERSION.json`.
The dedicated job retrieves that public digest, scans and signs it, and publishes
a separate `image-assurance/.../RUN-ATTEMPT` Release. It does not build an image,
change an exact image tag, rewrite the historical release record, or claim that
behavior tests ran again. The receipt distinguishes the original image source
from the workflow commit that generated these new observations.

Download `assurance-publication.json` from the completed workflow artifact, then
verify it against the consumer's already chosen digest:

```sh
python3 scripts/image_assurance.py verify-publication assurance-publication.json \
  --image ghcr.io/xormania/IMAGE@sha256:DIGEST --output /tmp/xorder-evidence
```

The publication descriptor is a locator, not trusted authority. The command
requires the consumer's exact pin and validates the trusted signer, digest,
predicate, public assets, and checksums. This manual path can establish new
assurance for a retained digest without inventing historical measurements.

## Retry and tool inputs

Evidence assets are named by their hashes. The receipt is uploaded last, before
`record.json`, so interrupted uploads cannot leave a durable record asserting
missing evidence. A retry with a staged receipt reuses its original observations
and verifies them again. It does not replace the scan date or database facts.
A retry interrupted before the receipt may create new observations and upload
new content-named assets. No existing asset is overwritten.

Cosign's installer is pinned to the official v4.1.0 commit
`ba7bc0a3fef59531c69a25acd34668d6d3fe6f22`, with cosign 3.1.3 explicitly
selected. The installer verifies its bootstrap hash and the requested release's
signatures. Trivy 0.75.0 is fetched from its exact official Linux amd64 asset and
verified against the published SHA-256 in `scripts/image_assurance.py`. No
mutable scanner installer script is executed. Vulnerability databases are
updated data inputs and their observations are preserved with each receipt.
Tool and database availability, Fulcio/Rekor/TUF access, and public GHCR
signature/OCI-referrer retrieval are real hosted execution gates. Local mocked
command tests cannot prove those services work together.

Primary references inspected for this integration:

- [Pinned cosign installer](https://github.com/sigstore/cosign-installer/blob/ba7bc0a3fef59531c69a25acd34668d6d3fe6f22/action.yml)
- [Cosign 3.1.3](https://github.com/sigstore/cosign/releases/tag/v3.1.3)
- [Sigstore container signing](https://docs.sigstore.dev/cosign/signing/signing_with_containers/)
- [Sigstore signature and attestation verification](https://docs.sigstore.dev/cosign/verifying/verify/)
- [Trivy 0.75.0 assets](https://github.com/aquasecurity/trivy/releases/tag/v0.75.0)
- [Trivy SBOM generation](https://trivy.dev/docs/latest/docs/supply-chain/sbom/)

## GitHub immutable Releases

Image publication prepares its inventory, scan, SBOM, signed receipt and durable
record in a draft before publishing. This ordering is compatible with locking
those assets at publication. HTTP resource publication currently makes payloads
public before anonymous verification and appends `record.json` afterwards.
Enabling repository-wide immutable Releases would prevent that existing path
from completing. This change does not alter that administrative setting.

A compatible future HTTP design would keep the payload in a public staging
location for anonymous verification, prepare every final payload/evidence asset
in a final draft, publish once, and perform final public checks without appending
or editing assets. Catalog acceptance must still verify the exact final URL and
bytes. The durable record must accurately distinguish the earlier staged-byte
observations from final-public-location checks, or store the latter in a separate
append-only evidence release. That format change needs its own design and tests;
turning on immutability alone is insufficient.

# Implementation status

xorder extends the existing image library with independently versioned binaries,
native environments, configuration, and context. The public repository URL
remains the discovery entry point; no installed helper, skill, plugin, or service
is required to read the catalog and follow a resource's usage page.

## Current source capabilities

The shared model validates resource definitions, verified release records,
profiles, and exact resolution locks. It generates the compact typed
[catalog](../catalog-v2.json), the unchanged schema-1 [image view](../catalog.json),
README availability tables, and the [downloadable resource index](resources/index.md)
from the accepted ledger. Detailed image inventories remain linked evidence.

The existing image families are `php-dev`, `php-browser`, `php-frankenphp`,
`flowbite-xor-dev`, `rust-dev`, and `python-dev`. PHP has 8.4 and 8.5 Trixie lines;
the Rust and Python lines are 1.99 and 3.14. Exact available revisions, measured
capabilities, platforms, and digests come from the catalog. The
[uxor usage profile](uxor.md) documents worker-mode PHP, Node 22,
cached Tailwind, and its project-locked official Playwright companion.

The authored non-image examples are an upstream Composer PHAR, a locked devenv
PHP/Symfony environment, EditorConfig, and sample Codex project guidance. The
[profiles](profiles.md) select a runtime, formatting, and optional targeted
context without also selecting Composer when the environment already supplies
it. The standalone Composer profile requires an existing compatible PHP runtime.
Definitions and profiles can exist before their releases become available.

Read-only resolution preserves supplied pins, selects compatible verified
releases for explicit target facts, and checks dependencies, cycles, version
conflicts, and overlapping destinations. Explicit local overlays keep private
assignments outside the public catalog. [Application](application.md) stages
verified HTTP bytes, caches by checksum, locks each target, records owned files,
and supports repeat application, conflict detection, recovery, rollback, and
explicit removal. Native backends own activation and service processes; images
are reported as external usage actions rather than falsely recorded as installed.

The publication adapters retain exact source tags and content identities,
verify anonymous public retrieval and behavior, and stage verified records
through protected-branch writeback. Selective CI distinguishes images, HTTP
resources, and native environments. Resource configuration/context changes do
not require unrelated image builds. Existing image refresh, measurements, aliases,
and release recovery continue to use their original contracts.

## Availability and verification evidence

Only accepted verified release records make resources selectable. Consult the
generated catalog and resource index for current availability; this authored
status document does not promote definitions or pending CI candidates. New
validation and publication paths in the source tree do not establish that their
CI runs have passed or that their HTTP releases have been accepted.

The historical
[source validation on 8 October 2026](https://github.com/xormania/docker-image-library/actions/runs/37713857904)
passed the initial six image build jobs and their behavior recipes: both PHP
runtimes and Panther interactions, Python/PostgreSQL, native/WASM Rust, mounted
file ownership, caches, and inventory validation. That run establishes source
validation on GitHub Actions, rather than registry publication or a live Claude
observation. Subsequent accepted image records retain their own publication,
anonymous-pull evidence, exact digests, timestamps, inventories, and measurements.
The old repository name in the historical run URL preserves its provenance.

[Discovery acceptance](discovery.md) combines independent requirement scenarios
with real execution fixtures. The bundle consumer fixture exercises authored
payloads through the public helper and a temporary controlled HTTPS endpoint;
its candidate records stay outside the accepted ledger. Image readiness,
Composer execution, native environment activation, and public retrieval require
their corresponding verification surfaces. File receipts establish delivery and
ownership; they do not establish that an agent followed delivered instructions.

The source-label rename remains a deliberate next-refresh image change, as
documented in [contributing](contributing.md). Portable PHP, Devbox, additional
platforms, and optional CDN mirrors can extend this structure. A live cloud-chat
observation can add evidence but is not a foundation acceptance prerequisite.

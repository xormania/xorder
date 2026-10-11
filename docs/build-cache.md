# Shared registry build cache

xorder's [composite action](../.github/actions/registry-build-cache/action.yml)
prepares the same GHCR build-cache references for a project's CI and local builds.
The consuming repository owns its Dockerfile, build context and build options.
The action supplies cache settings; it does not log in, build or publish an image.
It needs Bash and Python 3 on the runner.

For `xormania/uxor`, the package is `ghcr.io/xormania/uxor-cache`. Unprotected
branch builds and local imports reuse the current branch, a PR's base branch
where applicable, `dev`, `main`, and the actual default branch, without duplicates.
Protected CI builds import their protected current ref only by default. Additional
imports require explicit equal-protection assignments described below. A fork PR
omits its head branch. Ordinary packages use the lowercased repository name; unusual names that
GHCR cannot represent directly get a normalized name with a hash.

Tags `dev`, `main` and `master` stay readable. Every other branch gets a sanitized
prefix and a hash, so `feature/demo`, `feature-demo`, case differences and long
names keep separate caches. Optional `scope: demo` prefixes every tag, including
`demo-dev` and `demo-main`. Give independent build targets separate scopes, or
choose one writing shard, because multiple exports to one tag replace each other.
Docker documents [multiple cache imports and scoped export destinations](https://docs.docker.com/build/cache/backends/).

## CI integration

Add one cache-action step to the existing build job and pass its outputs into
the existing build action. Pin the xorder action to a reviewed commit. This Bake
example uses a project's `demo/` Compose files; choose the actual files and target.

```yaml
permissions:
  contents: read
  packages: write
steps:
  - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
  - uses: docker/setup-buildx-action@f87e5991a6d7451dcb8d9637bfbc97413f497069 # v4.4.1
  - id: registry-cache
    uses: xormania/xorder/.github/actions/registry-build-cache@PINNED_XORDER_COMMIT
    with:
      scope: demo
      # In a sharded build, set write: ${{ matrix.shard == 1 }}.
  - uses: docker/login-action@dbcb813823bdd20940b903addbd779551569679f # v4.6.0
    if: steps.registry-cache.outputs.write-enabled == 'true'
    with:
      registry: ghcr.io
      username: ${{ github.actor }}
      password: ${{ github.token }}
  - uses: docker/bake-action@018cb6412ab401ebaa809aa5f85966b74628600f # v7.4.0
    with:
      source: ./demo
      files: |
        compose.yaml
        compose.override.yaml
      targets: php
      load: true
      set: ${{ steps.registry-cache.outputs.bake-set }}
```

For `docker/build-push-action`, pass `cache-from` and `cache-to` outputs into its
same-named inputs. Keep image publication decisions in the consuming workflow.
The `bake-set` output clears inherited cache exports and imports before applying
the plan; use the whole output so read-only runs do not retain a consumer's
existing `cache-to` setting.

BuildKit caches are executable build inputs: cached intermediate layers can
replace steps that would otherwise run. A protected build therefore cannot trust
cache tags written by branches with weaker review or push protection. The action
uses GitHub's `GITHUB_REF_PROTECTED` fact to include only the protected current
ref. It does not assume that `dev`, `main`, or the default branch has equal trust.
`pull_request_target` always applies the restricted policy, excluding untrusted
head caches. If the protection fact is absent, imports default to the explicit
trusted list; an empty list produces a cold build.
GHCR access applies to the cache package, so tag names alone cannot prevent
another workflow with package write access from overwriting a protected cache.
Keep those credentials out of untrusted jobs, or use a separately authorized
package for protected builds when different writers cannot share trust.

To share cache between equally protected branches, verify their rules and the
permissions of every workflow able to write those tags, then configure:

```yaml
with:
  trusted-branches: |
    main
    release/stable
```

This is an owner-maintained assertion of equal protection, not automatic branch
protection discovery. Leave the input empty when that equality is not established.
The action needs no permission to query protection settings. The output's
`import-policy` is `protected-only` or `branch-reuse`; its actual `cache-from`
list records which tags will be consumed. Ordinary unprotected builds can still
write their own branch cache, but protected consumers do not import it implicitly.

Only a matching repository's nondeleted branch **push** enables a cache export.
PRs, fork PRs, `pull_request_target`, tags, schedules, manual workflows and local
commands import only. `write: false` also disables export, for reader shards.
The exporter explicitly sets
`type=registry,mode=max,image-manifest=true,oci-mediatypes=true`. Docker documents
these [registry-cache options](https://docs.docker.com/build/cache/backends/registry/).
They are an explicit compatible configuration, not a claim that GHCR uniquely
requires this manifest format.

Use `packages: write` and `GITHUB_TOKEN` in the writing workflow. On first publish,
confirm the package is associated with the repository, then make it public if
anonymous local and fork imports are intended. Packages start private; GitHub
documents [authentication and package association](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).
Private readers need separately authorized read access; public readers need no
registry credentials. Do not provide publishing credentials to fork builds.

For the first trusted push, retain the build log showing successful cache export,
inspect its manifest, and verify a subsequent build imports it. A missing cache
is a cold build, not an available released image. The helper does not claim a
runtime cache hit or a measured speedup.

## Local builds

Run from the consuming checkout, with the **same scope as its CI**. For Compose
2.24.4 or later, generate a read-only overlay and apply it last:

```sh
python3 "$XORDER_ROOT/scripts/build_cache.py" --repository xormania/uxor \
  --scope demo --format compose > /tmp/uxor-build-cache.yaml
docker compose --project-directory demo \
  -f demo/compose.yaml -f demo/compose.override.yaml \
  -f /tmp/uxor-build-cache.yaml build php
```

The overlay replaces that service's imports and removes its inherited exports
with Compose's documented [`!override` and `!reset` tags](https://docs.docker.com/reference/compose-file/merge/).
Build only the selected service; other services retain their own configuration.
Use `--branch BRANCH` for detached checkouts and `--default-branch master` for
repositories whose default branch is `master`. `--format buildx` prints
`--cache-from` arguments, `--format bake` prints overrides that clear all inherited
exports, and the default JSON format exposes the complete read-only plan.
For a local build requiring the same restricted policy, add `--protected` and
repeat `--trusted-branch BRANCH` for the cache branches whose protection was
verified. An empty explicit list disables registry imports; local commands
remain read-only under both policies.

To warm a locally built xorder image from a matching CI cache:

```sh
python3 scripts/build.py python-dev/3.14-trixie local:python \
  --registry-cache xormania/xorder --cache-scope python
```

These imports are opt-in and coexist with the existing local directory cache.
They never add a registry exporter. Registry caching needs a capable Buildx
builder: the default Docker driver supports it with the containerd image store;
otherwise use a compatible driver. Local parent-image builds still use the
daemon's builder, so that builder must support registry cache if imports are used.
The UXor runner already starts its pinned prepared image with `--no-build` and
binds the checkout; it does not need an app-image rebuild to start another worktree.

## Secrets, visibility and renames

Treat `mode=max` cache contents as published build layers, including intermediate
stages. In each consumer's effective `.dockerignore`, exclude `.env.local`,
`.env.*.local`, `**/.env.local` and `**/.env.*.local`, plus its other credentials.
A [Dockerfile-specific ignore file takes precedence](https://docs.docker.com/build/concepts/context/#dockerignore-files),
so check the actual build context and ignore file. Pass required credentials through
[BuildKit secret mounts](https://docs.docker.com/build/building/secrets/), and keep
them out of copied/generated files and build arguments. Local imports do not grant
permission to publish layers from a private checkout.

The action derives the package from `github.repository` on every run. A repository
rename therefore creates a different cache package; a run started before the
rename can still write the old one. Establish and inspect the new cache before
reviewing and deleting the old cache package in GitHub package settings. Do not
delete published runtime image packages or their exact release identities as
part of cache cleanup. The action does not rename or delete packages automatically.

As checked on 2026-10-11, GitHub states that GHCR container storage and bandwidth
are [currently free](https://docs.github.com/en/billing/concepts/product-billing/github-packages),
including private containers. Public visibility enables anonymous access; it is
not currently necessary to avoid a private-container storage charge.

# Profiles and target assignments

A profile selects independent resources for a task. It does not rebuild them or
turn context into executable capabilities. The initial
[`profile/php-project`](../profiles/php-project.json) chooses:

| Role | Exact resource revision | Reason |
| --- | --- | --- |
| Runtime | `environment/php-symfony` 1.0.0 | PHP and Composer supplied by a locked devenv environment |
| Formatting | `configuration/editorconfig` 1.0.0 | Project-local formatting configuration |
| Project context | `context/project-guidance` 1.0.0, optional | Example guidance for a target with `harness: codex` and `scope: project` |

The standalone Composer resource is not also selected because the environment
already supplies Composer. Different roles can select alternatives, but a
resolver chooses at most one alternative for each role. A profile can exist
before all its exact components have been published; it is usable only when
every required role resolves to an available verified release.

## General bases to specific uses

The generated [capability guide](capabilities.md) groups resources by applicability
and links the current release beside each reusable pinned profile. These groups
are navigation, not inheritance or automatic selection. The added profiles are:

| Profile | Intended use |
| --- | --- |
| [`php-base`](../profiles/php-base.json) | General PHP 8.5 CLI development |
| [`python-base`](../profiles/python-base.json) | General Python 3.14 development |
| [`rust-base`](../profiles/rust-base.json) | General Rust 1.99 development |
| [`php-http`](../profiles/php-http.json) | PHP 8.5/Symfony HTTP and workers |
| [`uxor`](../profiles/uxor.json) | Existing uxor checkout with the project runner |

These new profiles pin currently verified image revisions explicitly. Existing
profiles keep their intentional older exact revisions. The uxor profile selects
its application image only; its runner independently verifies the official browser
version against the project lock. It does not assert a catalog browser matches
every Playwright release. A profile lock selects images; the usage runner manages
them, because the file application helper does not install an OCI engine or image.

## Resolve before applying

Start with the [README](../README.md), inspect the project's requirements, and
read each selected resource's usage page. Check the
[typed catalog](../catalog-v2.json) for exact revisions and prerequisites.
Explicit target facts determine which assignments apply. For example:

```json
{
  "platform": "linux/amd64",
  "scope": "project",
  "harness": "codex",
  "commands": ["nix", "devenv"]
}
```

These facts are an example, not detected facts about the reader's machine.
Inspect the target before recording them. The Codex context role requires both
conditions; omit it on a different harness. Missing facts and missing
prerequisites should be reported precisely, rather than replaced with guessed
capabilities or extra bundles.

The resolution lock records exact resource revisions and content identities
for the selected target. The environment's native `devenv.lock` separately pins
its Nix inputs. Neither lock replaces the consuming application's own dependency
lockfiles. Retain a project's existing exact pins until deliberately updating.

With a trusted checkout of xorder and the inspected facts in `target.json`, the
optional Python helper can resolve the profile and save the exact lock:

```sh
python3 scripts/xorder_cli.py resolve profiles/php-project.json \
  --target target.json --output php-project.lock.json
python3 scripts/xorder_cli.py plan php-project.lock.json --root /path/to/project
python3 scripts/xorder_cli.py apply php-project.lock.json --root /path/to/project
python3 scripts/xorder_cli.py verify --root /path/to/project
```

Continue to plan and apply only after resolution succeeds. An unavailable
required release cannot produce a usable lock. The helper runs on Python 3 and
the initial tested application surface is Linux. To retain prior resource pins,
pass `--pins php-project.lock.json` during resolution. Add an explicit private
assignment file with `--overlay private-assignments.json` when one is wanted.
The helper is a convenience; direct usage is documented on each resource page.

Review an installation plan before applying it. Materialize only the selected
files under the selected project or user root; retain an installation receipt
for the files placed there. Runtime activation remains the environment's
documented procedure. The same target-side procedure can run on a machine,
inside a container, or through an existing SSH connection.

## Keep reusable content separate from private assignments

Public profiles describe reusable setups. Private machine names, addresses,
credentials and user-specific choices belong in an explicit local or private
overlay. Overlay assignments can select existing resources without copying
their payloads into a second source of truth. No central fleet server is needed.

Configuration and context files update independently of the runtime. Reapplying
the same content should retain the same owned bytes. A local edit or an unowned
destination is a conflict. Resolve it explicitly before updating, removing or
rolling back owned files. Context receipt evidence establishes delivery;
instruction following requires a separate observation in the consuming agent.

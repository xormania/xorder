# Discovery from the repository URL

Give a fresh chat [the repository URL](https://github.com/xormania/xorder) and its
project task. The [README](../README.md) is the entry point. It leads to the [capability guide](capabilities.md) and compact
[current index](../discovery.json), then a resource's usage page and exact release
evidence. [catalog-v2.json](../catalog-v2.json) retains full release history;
image package inventories are loaded only when relevant. GitHub-rendered pages and their raw files carry the same information.
No installed xorder command, skill, plugin or discovery service is required.

The agent should inspect the project's runtime constraints, extensions,
dependency locks, services and test needs; inspect the current execution
environment; then select an `available` resource whose prerequisites and measured
target match. Preserve existing compatible pins. Follow the usage page's
readiness command before installing the application's own locked dependencies.
Report missing requirements specifically rather than guessing a tag or treating
an authored definition as a published release.

Reading a catalog does not activate context. Context is selected for an explicit
audience and scope; an existing project instruction file remains a project-owned
decision. Configuration, context and runtime resources have independent versions.
The [profiles page](profiles.md) explains composition, explicit target facts and
private assignment overlays. The optional helper exposes the same model.

## What acceptance establishes

Image consumer requirements in [`tests/requirements/`](../tests/requirements)
are independent selection scenarios. Runtime fixtures execute the selected
images and locked environments. Unit checks cover general resolver, transport
and target ownership rules, including missing prerequisites, retained pins,
conflicts and interrupted application.

The separate
[application consumer fixture](../tests/fixtures/artifacts/application/check.py)
exercises the real authored EditorConfig and sample Codex context, rather than
synthetic installer payloads. It packages them with the publication helper,
retrieves their exact hashes over a temporary loopback HTTPS endpoint, and runs
the same trusted resource exercise used by publication. Only after those checks
pass does it create candidate metadata inside its temporary fixture directory,
with the verification surface explicitly recorded as `controlled-fixture`.
These records never enter the repository's accepted release ledger.

The fixture then drives the public Python CLI to resolve the authored PHP profile
and apply its configuration and context from a cold cache. A fixture-local
overlay makes the runtime role optional because this candidate catalog contains
only the two exercised file resources. Native environment and image runtime
acceptance remain separate checks; this fixture does not simulate either.

[`resource-application.json`](../tests/requirements/resource-application.json)
states independent expected destinations and assignments. The fixture checks
actual installed bytes, unchanged repeat application without timestamp/inode
changes, receipt verification, Codex/project scope, other-harness context
exclusion, preservation of unrelated files and an unowned `AGENTS.md`, and
conflict handling before any partial installation.

On a Linux amd64 host with Python, the validation dependencies, Git, OpenSSL and
a system CA bundle, run:

```sh
python3 -m pip install -r requirements-ci.txt
python3 tests/fixtures/artifacts/application/check.py \
  --output out/application-consumer.json
```

The fixture adds its short-lived test certificate to a temporary copy of the
system trust bundle and restores the process's trust setting afterward. It does
not change system trust. The same command can run in a disposable verified
Python image with this checkout mounted; container execution evidence belongs
to the CI run, rather than being inferred from a successful host execution.

## What remains a separate observation

These deterministic checks establish that the published information supports
selection and that the delivery commands exercise the documented behavior.
They do not establish that a particular cloud chat fetched the URL, that every
vendor execution surface permits downloads or containers, or that a model
followed a delivered instruction file. A later real cloud-agent run can add that
evidence. The separate [agent evaluations](agent-evaluations.md) record actual
setup, reuse and recovery outcomes with explicit harness/model and execution
surface facts. A live chat is not an acceptance prerequisite for this foundation.

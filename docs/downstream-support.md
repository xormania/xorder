# Downstream release-group support checks

Projects select a release group and pin its image artifacts. The group owns the
support dates; the image digest owns the software identity. Reusing the same
digest in a later accepted group does not build another image. Updating a project
to that group still requires a deliberate lock change and project validation.

The default schedule is a Monday 06:00 UTC release slot, 28 days of support,
a warning seven days before expiry, and a further 14 days before removal becomes
eligible. Actual dates belong to accepted groups in
[`lifecycle/release-groups.json`](../lifecycle/release-groups.json).
An accepted group never grants indefinite retention to a downstream pin.

## Adopt a project lock

Choose an accepted group, select the image resources your project uses, and
commit `xorder-support.lock.json` at the project root. Copy the exact line,
revision, registry digest and verified platform from that group's resources.
`service` links the selection to a Compose service in the UXor runner. The lock
can select a subset of the group; each resource must match it exactly.

This example shows the shape only. Replace the group, revision and digest from
accepted policy before use; the placeholder is intentionally not a pullable pin.

```json
{
  "schema_version": 1,
  "group": "ACCEPTED-GROUP-ID",
  "resources": [
    {
      "line_id": "uxor-dev/8.5-trixie",
      "version": "ACCEPTED-REVISION",
      "identity": "ghcr.io/xormania/uxor-dev@sha256:ACCEPTED-DIGEST",
      "platform": "linux/amd64",
      "service": "php"
    }
  ]
}
```

Declare every selected xorder image service, including the browser when using
the xorder Playwright image. External database and upstream browser images remain
the consumer's responsibility. Put the locked identities in the actual project
image selection as well. A lock is not evidence that Docker used those bytes.

An explicit `XORDER_SUPPORT_LOCK` selects another lock path, relative to the
project root or absolute. An explicitly selected missing file fails. An announced
`legacy.enforce_after` date starts bounded migration for projects without locks:
they receive an adoption warning before that date and fail on workload use at
the deadline. Before any rollout is announced, an existing project with no lock
keeps its current behavior. Announcing the date and supplying an accepted initial
group are part of rollout; source implementation alone does not publish a group.

## Check in any project's CI

After making the selected images available on the chosen Docker engine:

```sh
python3 /path/to/xorder/scripts/xorder_cli.py support-check \
  --lock xorder-support.lock.json \
  --image php="$IMAGE" --image browser="$BROWSER_IMAGE"
```

Supply only the services declared by that project's lock. Tags and compatible
aliases are accepted observation inputs: Docker's actual `RepoDigests` and image
platform are checked against the lock and accepted group. Local image IDs, tag
names, labels, and a digest copied out of the lock are insufficient evidence.
An accepted group's index digest or its verified platform manifest can match.
An image without engine-observed repository digests fails with a pull instruction.
The check command does not pull images or start services.

Other CI engines can collect their own image observations and supply `--actual
actual-images.json` instead of `--image`. That file is a JSON list with
`line_id`, `identity`, `platform`, and the matching optional `service` for every
lock entry. Obtain its values from the actual selected image or running workload;
do not manufacture the file from the selection lock.

The stdlib-only entry point exposes the same check without the discovery helper's
dependencies:

```sh
python3 /path/to/xorder/scripts/xorder/downstream.py check \
  --lock xorder-support.lock.json --image php="$IMAGE"
```

Both entry points return exit 0 for a supported group or its warning window and
exit 2 for an expired group, missing or invalid policy, missing observation,
wrong artifact/platform, or selection outside the accepted group. JSON includes
the expiry, replacement group when available, and migration action. Connect this
check as a required CI gate before project commands. A scheduled downstream CI
check makes deadlines visible even when the project has no new commits.

## Fresh policy and bounded offline CI

Each online check fetches the current public policy from
`https://raw.githubusercontent.com/xormania/xorder/master/lifecycle/release-groups.json`.
The lock cannot supply its own support policy. The fetch uses no GitHub token,
authentication or cookies, refuses redirects and noncanonical URLs, requests
cache revalidation, and bounds transfer size and connection/read time. Neither
an old checkout nor a policy pinned to an old commit establishes current support.
Allow this public endpoint in environments that restrict outbound requests.

For offline CI, fetch an explicit snapshot while connected:

```sh
python3 /path/to/xorder/scripts/xorder_cli.py support-fetch \
  --output current-support-policy.json
python3 /path/to/xorder/scripts/xorder_cli.py support-check \
  --policy-file current-support-policy.json \
  --lock xorder-support.lock.json --image php="$IMAGE"
```

The snapshot contains the policy, canonical source, actual acquisition time,
declared `valid_until`, and a hash of the policy content. It is valid for at most
24 hours. Expired snapshots, future acquisition dates, extended validity,
changed content and bare authored policy files fail. A shorter freshness period
in current policy also applies. An offline snapshot is explicitly trusted local
CI input; its receipt does not claim a signature or protect against an operator
deliberately rewriting both the policy and receipt. Fetch it in the trusted
acquisition job and carry it into the offline job as that job's artifact.

`--policy-url` accepts only the canonical public master endpoint and its
`refs/heads/master` spelling. `XORDER_SUPPORT_POLICY_FILE` and
`XORDER_SUPPORT_POLICY_URL` provide the same explicit source choice to the runner.
An opted-in project fails when a current policy cannot be obtained, rather than
silently treating an old policy embedded in the lock as current.

## UXor startup and existing containers

The UXor runner validates current group support before any large image pull,
runs the startup disk preflight, and explicitly pulls missing locked service
images through Compose. It then checks selected image identities before starting Compose services
and checks the actual running container image IDs before setup, tests, PHP tasks,
sync, cache operations or `exec`. A cached image is checked just like a freshly
pulled one. The post-start observation catches a retained container whose actual
image differs from the new selection. `xr support` prints the current report
without invoking project hooks:

```sh
python3 /path/to/xorder/scripts/xr.py /path/to/project support
```

Support checks do not interrupt an arbitrary already-running container at the
deadline. They fail when the enforced runner or CI gate is used. `status`, logs,
cleanup and `down` remain usable for diagnosis and recovery. Direct Docker use
outside these gates cannot be controlled by a client-side policy check; install
the reusable gate at every downstream execution entry point you require.

Xorder's upstream source validation uses an explicit builder-provenance hook
for unpublished local images. It binds the source commit and every observed
service image ID. The trusted build verifier creates the candidate proof for
source checks and anonymous publication assurance. The fixture validates that
candidate, resolves its pinned companion, and records the exact PHP and browser
IDs outside the mounted consumer checkout. The runner verifies those IDs and
the validating xorder checkout's commit; parity's minimal environment receives
only that prepared proof path. Ordinary downstream startup does not receive a blanket
environment-variable exemption. Source validation establishes candidate behavior;
it does not claim that an unpublished candidate belongs to a supported group.

Before expiry, validate the replacement group against the project and update
the group, required image revisions and actual digest selections together in a
PR. A shared unchanged digest can remain the same while the supported group
advances. At expiry, the old group fails even if Docker has cached its artifacts
and the registry still retains them during the removal grace period.

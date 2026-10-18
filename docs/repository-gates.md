# Repository release gates

Read-only audit on 18 October 2026 found the active master ruleset
[24688880](https://github.com/xormania/xorder/rules/24688880) requires PRs,
resolved review threads, and the `checks` and `catalog-evidence` status contexts.
The source change that introduces `attribution-policy` cannot make that external
context required by itself; an administrator must add it after its first real
run.

The stable checks to require are `checks` (Validate's aggregate metadata/runtime
result), `catalog-evidence` (public release facts, immutable historical records,
and signatures for new assured records), and `attribution-policy` (the full
reachable-history and pull-request metadata audit). The attribution workflow is
base-controlled: it treats a proposed head as Git data and never checks out or
executes pull-request code, then publishes its explicit check on that exact
head. All three checks run on every PR, and their names do not depend on image
matrix size. Keep these contexts stable when changing individual job structure.
Select GitHub Actions as the expected source in the settings UI after each has
produced a real run.

This public repository must also explicitly allow
`.github/workflows/attribution.yml` to use the `pull_request_target` event in its
Actions execution policy before GitHub's default block becomes enforced on
2 November 2026. The workflow grants only read access to contents and permission
to report its explicit head check; proposed Git objects are parsed as data and
never checked out or executed. Do not require `attribution-policy` until both
the event policy and a real pull-request check have been verified.
The live check-run audit observed GitHub Actions app ID `15368`; the REST
proposal binds newly added contexts to that source rather than accepting any
non-Actions status publisher. Existing contexts and their source IDs remain
unchanged. This source binding identifies the GitHub Actions app, not a specific
workflow: another repository workflow with write permission can publish the
same check name. On a user-owned repository, treat this as a strong accidental
change guard, not an adversarially unspoofable gate. Hard enforcement against a
hostile same-repository workflow requires a separately installed GitHub App as
the expected source, or an organization/enterprise ruleset that requires the
specific workflow.

The check is attached to the proposed head commit, so it cannot inspect a merge
or squash commit whose message is edited in the GitHub merge dialog after the
check runs. Pull-request title and body edits also keep the same head SHA; the
`edited` trigger requests a fresh audit but cannot make that queueing interval
atomic. Review the final merge text, and add native ruleset restrictions for
commit messages plus author and committer email patterns as defense in depth.
Test those restrictions in evaluate mode first: a broad provider-domain rule
would also reject accountable people who work for a provider, which is outside
this policy. The scheduled full-history audit detects anything that reaches
master despite these pre-merge controls.

An administrator can use the ruleset UI to require all three contexts and decide
whether branches must be up to date. To prepare a reviewable REST update while
preserving other current settings:

```sh
mkdir -p out/admin
# Fetch again at the time of review; the audit snapshot can become stale.
gh api repos/xormania/xorder/rulesets/24688880 > out/admin/master-ruleset-observed.json
# Replace PR_HEAD_SHA with the reviewed PR's exact head; recheck all three contexts and sources.
gh api repos/xormania/xorder/commits/PR_HEAD_SHA/check-runs \
  --jq '.check_runs[] | select(.name == "checks" or .name == "catalog-evidence" or .name == "attribution-policy") | {name, app_id: .app.id, app_slug: .app.slug, status, conclusion}'
python3 - <<'PY'
import json
from pathlib import Path
folder = Path('out/admin')
observed = json.loads((folder / 'master-ruleset-observed.json').read_text())
allowed = {'name', 'target', 'enforcement', 'conditions', 'rules', 'bypass_actors'}
proposal = {key: value for key, value in observed.items() if key in allowed}
status_rules = [rule for rule in proposal['rules'] if rule['type'] == 'required_status_checks']
if len(status_rules) != 1:
    raise SystemExit('Current ruleset structure changed; inspect it before editing')
checks = status_rules[0]['parameters']['required_status_checks']
existing = {check['context'] for check in checks}
for context in ('checks', 'catalog-evidence', 'attribution-policy'):
    if context not in existing:
        checks.append({'context': context, 'integration_id': 15368})
(folder / 'master-ruleset-proposed.json').write_text(json.dumps(proposal, indent=2) + '\n')
PY
diff -u out/admin/master-ruleset-observed.json out/admin/master-ruleset-proposed.json || true
```

After reviewing the generated proposal, the contexts' real workflow results,
and that all three report app ID `15368` and slug `github-actions`,
an administrator can apply it with:

```sh
gh api --method PUT repos/xormania/xorder/rulesets/24688880 \
  --input out/admin/master-ruleset-proposed.json
```

The payload preserves the observed strictness, bypass actors, review controls,
merge methods and other rules. The command deliberately requires separate admin
execution; repository source and generated docs cannot enforce external settings.
Re-read the ruleset after applying and confirm the expected check sources in the
UI. Requiring check names without allowing their workflows to run can block every
PR, including catalog proposals made with `GITHUB_TOKEN` until their workflows
are approved.

Official references: [ruleset REST update](https://docs.github.com/en/rest/repos/rules#update-a-repository-ruleset),
[required status checks](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches#require-status-checks-before-merging),
[ruleset workflow behavior](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/troubleshooting-rules),
[commit metadata restrictions](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository#using-regular-expressions-for-commit-metadata),
and [secure `pull_request_target` use](https://docs.github.com/en/actions/reference/security/securely-using-pull_request_target).

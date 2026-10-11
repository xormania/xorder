# Repository release gates

Read-only audit on 11 October 2026 found the active master ruleset
[24688880](https://github.com/xormania/xorder/rules/24688880) requires PRs and
resolved review threads, but its `required_status_checks` list is empty.
Therefore workflow success is visible evidence, not currently a ruleset-enforced
merge condition. This document proposes the settings; no settings were changed.

The stable checks to require are `checks` (Validate's aggregate metadata/runtime
result) and `catalog-evidence` (public release facts, immutable historical
records, and signatures for new assured records). Both workflows run on every
PR, and their job names do not depend on image matrix size. Keep these contexts
stable when changing individual job structure. Select GitHub Actions as the
expected source in the settings UI after both have produced a real run.
The live check-run audit observed GitHub Actions app ID `15368`; the REST
proposal binds newly added contexts to that source rather than accepting any
status publisher. Existing contexts and their source IDs remain unchanged.

An administrator can use the ruleset UI to require both contexts and decide
whether branches must be up to date. To prepare a reviewable REST update while
preserving other current settings:

```sh
mkdir -p out/admin
# Fetch again at the time of review; the audit snapshot can become stale.
gh api repos/xormania/xorder/rulesets/24688880 > out/admin/master-ruleset-observed.json
# Replace PR_HEAD_SHA with the reviewed PR's exact head; recheck both sources.
gh api repos/xormania/xorder/commits/PR_HEAD_SHA/check-runs \
  --jq '.check_runs[] | select(.name == "checks" or .name == "catalog-evidence") | {name, app_id: .app.id, app_slug: .app.slug, status, conclusion}'
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
for context in ('checks', 'catalog-evidence'):
    if context not in existing:
        checks.append({'context': context, 'integration_id': 15368})
(folder / 'master-ruleset-proposed.json').write_text(json.dumps(proposal, indent=2) + '\n')
PY
diff -u out/admin/master-ruleset-observed.json out/admin/master-ruleset-proposed.json || true
```

After reviewing the generated proposal, the contexts' real workflow results,
and that both report app ID `15368` and slug `github-actions`,
an administrator can apply it with:

```sh
gh api --method PUT repos/xormania/xorder/rulesets/24688880 \
  --input out/admin/master-ruleset-proposed.json
```

The payload preserves the observed strictness, bypass actors, review controls,
merge methods and other rules. The command deliberately requires separate admin
execution; repository source and generated docs cannot enforce external settings.
Re-read the ruleset after applying and confirm the expected check sources in the
UI. Requiring job names without allowing their workflows to run can block every
PR, including catalog proposals made with `GITHUB_TOKEN` until their workflows
are approved.

Official references: [ruleset REST update](https://docs.github.com/en/rest/repos/rules#update-a-repository-ruleset),
[required status checks](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches#require-status-checks-before-merging).

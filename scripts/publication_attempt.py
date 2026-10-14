"""Reserve one immutable publication attempt before building an image."""
import copy
import json
import re
from pathlib import Path

from artifact_identity import build_key, _reference as exact_reference


def validate_attempt(value, definition, parent, root):
    if (not isinstance(value, dict) or value.get('schema_version') != 1
            or value.get('line_id') != definition['line_id']
            or value.get('version') != definition['revision']
            or not re.fullmatch(r'[a-f0-9]{40}', str(value.get('source_commit', '')))
            or value.get('build_key') != build_key(definition, root=root, parent=parent)):
        raise ValueError('Publication attempt differs from the requested build inputs; allocate a new revision')
    frozen = value.get('definition')
    if (not isinstance(frozen, dict) or frozen.get('line_id') != value['line_id']
            or frozen.get('revision') != value['version'] or not isinstance(value.get('tools'), dict)
            or exact_reference(value.get('resolved_base')) != exact_reference(
                parent or definition['base']['tag'] + '@' + definition['base']['digest'])
            or build_key(frozen, root=root, parent=parent, tools=value['tools']) != value['build_key']
            or not re.fullmatch(r'[a-f0-9]{64}', str(value.get('input_fingerprint', '')))):
        raise ValueError('Publication attempt contains inconsistent frozen inputs')
    expected = f"ghcr.io/xormania/{definition['family']}:{definition['line']}-candidate-v{definition['revision']}-{value['build_key']}"
    if value.get('candidate') != expected:
        raise ValueError('Publication candidate does not identify its reserved build inputs')
    return value


def reserve(definition, source, parent, destination, *, root, tools, fingerprint,
            gh, run, encoded, now, repository):
    if not re.fullmatch(r'[a-f0-9]{40}', str(source)):
        raise ValueError('Publication needs an exact source commit')
    tag = f"{definition['line_id']}/v{definition['revision']}"
    releases = json.loads(gh('api', '--paginate', '--slurp', f'repos/{repository}/releases'))
    matching = [release for page in releases for release in page if release['tag_name'] == tag]
    if len(matching) > 1:
        raise ValueError('Multiple Releases claim the same publication attempt')
    path = Path(destination) / 'candidate.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    if matching:
        release = matching[0]
        if not any(asset['name'] == 'candidate.json' for asset in release['assets']):
            raise ValueError('Release exists without a reserved candidate receipt; recover it or allocate a new revision')
        path.unlink(missing_ok=True)
        run('gh', 'release', 'download', tag, '--pattern', 'candidate.json', '--dir', str(path.parent))
        value = validate_attempt(json.loads(path.read_text()), definition, parent, root)
        if release['target_commitish'] != value['source_commit']:
            raise ValueError('Publication receipt source differs from its Release target')
        return value
    key = build_key(definition, root=root, parent=parent)
    value = {'schema_version': 1, 'line_id': definition['line_id'], 'version': definition['revision'],
             'source_commit': source, 'build_key': key, 'created_at': now(),
             'resolved_base': parent or definition['base']['tag'] + '@' + definition['base']['digest'],
             'definition': copy.deepcopy(definition), 'tools': copy.deepcopy(tools),
             'input_fingerprint': fingerprint,
             'candidate': f"ghcr.io/xormania/{definition['family']}:{definition['line']}-candidate-v{definition['revision']}-{key}"}
    validate_attempt(value, definition, parent, root)
    run('gh', 'release', 'create', tag, '--target', source, '--draft', '--title', tag,
        '--notes', 'Reserved build inputs. The exact artifact is awaiting build, verification and assurance.')
    path.write_text(encoded(value))
    run('gh', 'release', 'upload', tag, str(path))
    return value

#!/usr/bin/env python3
"""Reject AI-persona attribution in commits and pull-request metadata.

The full-history audit inspects every commit reachable from HEAD.  A range mode
is also available for local diagnostics.  Ordinary discussion of AI tools is
allowed; message checks are limited to identity trailers, session metadata/URLs,
and attribution-shaped signatures.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


AI_IDENTITY_NAME = re.compile(
    r"^\s*(?:"
    r"(?:anthropic[\s-]+)?claude"
    r"(?:[\s-]+(?:\(?ai\)?|code|assistant|agent|opus|sonnet|haiku|bot|automation|"
    r"action|app|review|v?[0-9][a-z0-9._-]*))*"
    r"(?:\s*\[bot\])?"
    r"|(?:openai[\s-]+)?(?:gpt[\s-]*[0-9]+(?:\.[0-9]+)?[\s-]+)?codex"
    r"(?:[\s-]+(?:\(?ai\)?|cli|assistant|agent|bot|automation|action|app|review|"
    r"v?[0-9][a-z0-9._-]*))*(?:\s*\[bot\])?"
    r"|(?:x[.\s-]?ai[\s-]+)?grok"
    r"(?:[\s-]+(?:\(?ai\)?|code|assistant|agent|bot|automation|action|app|review|"
    r"[0-9][a-z0-9._-]*))*(?:\s*\[bot\])?"
    r"|(?:anthropic(?:[\s-]+ai)?|openai|x[.\s-]?ai)"
    r"(?:[\s-]+(?:assistant|agent|bot|automation|action|app))?(?:\s*\[bot\])?"
    r"|openai[\s-]+gpt[\s-]*[0-9]+(?:\.[0-9]+)?(?:\s*\[bot\])?"
    r")\s*$",
    re.IGNORECASE,
)
AI_BOT_IDENTITY_NAME = re.compile(
    r"^\s*(?:anthropic|claude|openai|codex|x[.-]?ai|grok)"
    r"(?:[-_.\s]+[a-z0-9]+)*\s*\[bot\]\s*$",
    re.IGNORECASE,
)
AI_IDENTITY_EMAIL = re.compile(
    r"^(?:"
    r"(?:claude(?:[-.+](?:code|ai|bot))*|noreply(?:[+.-]claude(?:[-.]code)?)?)"
    r"@(?:noreply\.)?anthropic\.com"
    r"|(?:codex(?:[-.+](?:cli|bot))*|noreply(?:[+.-]codex)?)"
    r"@(?:noreply\.)?openai\.com"
    r"|(?:grok(?:[-.+]bot)*|noreply(?:[+.-]grok)?)"
    r"@(?:noreply\.)?(?:x\.ai|xai\.com|grok\.com)"
    r"|(?:[0-9]+\+)?(?:anthropic|claude|openai|codex|xai|x-ai|grok)"
    r"(?:[-_.][a-z0-9]+)*\[bot\]"
    r"@(?:users\.noreply\.github\.com|noreply\.github\.com|noreply\.gitlab\.com)"
    r")$",
    re.IGNORECASE,
)
DEPENDABOT_IDENTITY = re.compile(r"^dependabot(?:-preview)?(?:\[bot\])?$", re.IGNORECASE)
BY_TRAILER = re.compile(
    r"^\s*(?P<key>[a-z][a-z0-9-]*-by)\s*:\s*(?P<value>\S.*)?\s*$",
    re.IGNORECASE,
)
TRAILER_IDENTITY = re.compile(
    r"^(?P<name>.*?)\s*<(?P<email>[^<>]+)>(?:\s+.*)?$",
)
AI_METADATA_TRAILER = re.compile(
    r"^\s*(?P<key>(?P<product>"
    r"claude(?:[-_]code)?|anthropic(?:[-_]claude(?:[-_]code)?)?|"
    r"(?:openai[-_])?codex|openai|grok|x[.-]?ai(?:[-_]grok)?"
    r")[-_](?P<kind>session|task)(?:[-_](?P<qualifier>id|url|link))?)"
    r"\s*:\s*(?P<value>\S.*)?\s*$",
    re.IGNORECASE,
)
ATTRIBUTION_SIGNATURE = re.compile(
    r"^\s*(?:>\s*)?(?:[-+*]\s+)?(?:🤖\s*)?(?:\*\*|__|\*|_)?"
    r"(?:ai[-_ ]+)?"
    r"(?:this\s+(?:commit|change|pull\s+request)\s+"
    r"(?:was\s+)?)?(?:(?:generated|created|built|authored|written|produced|made|implemented|co-authored)"
    r"[-_ ](?:with|by|using|via)|assisted[-_ ]by|powered[-_ ]by)"
    r"(?:\s*:\s*|\s+)(?P<target>\S.*)$",
    re.IGNORECASE,
)
SESSION_URL = re.compile(
    r"https?://(?:"
    r"(?:www\.)?claude\.ai/(?:code/session(?:s)?[/_]|share/)"
    r"|(?:www\.)?chatgpt\.com/(?:codex/(?:task|tasks|session|sessions)/|share/)"
    r"|chat\.openai\.com/share/"
    r"|(?:www\.)?grok\.com/(?:share|session)/"
    r"|(?:www\.)?x\.com/i/grok/(?:share|session)/"
    r")",
    re.IGNORECASE,
)
FENCE_START = re.compile(r"^ {0,3}(?P<marker>`{3,}|~{3,})")
OPAQUE_METADATA_ID = re.compile(
    r"^(?:(?:session|task|thread|conversation)[_:/-][a-z0-9._:/-]+|"
    r"[a-z0-9._:/-]*[0-9][a-z0-9._:/-]*)$",
    re.IGNORECASE,
)


class AttributionCheckError(RuntimeError):
    """A malformed invocation or repository prevented a trustworthy check."""


@dataclass(frozen=True)
class Finding:
    source: str
    kind: str
    detail: str

    def diagnostic(self):
        return f"{self.source}: {self.kind}: {self.detail}"


def _git(repository, *arguments, allowed=(0,)):
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        capture_output=True,
        text=True,
        errors="replace",
    )
    if result.returncode not in allowed:
        error = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise AttributionCheckError(f"git {' '.join(arguments)} failed: {error}")
    return result


def _resolve_commit(repository, revision, label):
    if not revision:
        raise AttributionCheckError(f"{label} revision is empty")
    result = _git(
        repository,
        "rev-parse",
        "--verify",
        "--end-of-options",
        f"{revision}^{{commit}}",
        allowed=(0, 128),
    )
    if result.returncode:
        raise AttributionCheckError(f"{label} is not a known commit: {revision}")
    return result.stdout.strip()


def _without_markup(value):
    """Return a compact attribution target without common Markdown wrappers."""
    candidate = value.strip()
    candidate = candidate.rstrip(".,;:!?").strip()
    for _ in range(3):
        changed = False
        for opening, closing in (("**", "**"), ("__", "__"), ("`", "`"), ("*", "*"), ("_", "_")):
            if candidate.startswith(opening) and candidate.endswith(closing):
                candidate = candidate[len(opening):-len(closing)].strip()
                changed = True
                break
        link = re.match(r"^\[(?P<label>[^]]+)]\s*(?:\([^)]*\)|\[[^]]*])", candidate)
        if link:
            candidate = link.group("label").strip()
            changed = True
        if not changed:
            break
    return " ".join(candidate.split())


def _name_candidates(name):
    """Yield a name and versions with trailing human-readable annotations removed."""
    candidate = _without_markup(name)
    yield candidate
    while True:
        stripped = re.sub(r"\s*(?:\([^()]*\)|\[[^][\]]*])\s*$", "", candidate).strip()
        if stripped == candidate:
            return
        candidate = stripped
        yield candidate


def _identity_label(name, email):
    name_match = next(
        (match for candidate in _name_candidates(name)
         if (match := (
             AI_IDENTITY_NAME.fullmatch(candidate)
             or AI_BOT_IDENTITY_NAME.fullmatch(candidate)
         ))),
        None,
    )
    email_match = AI_IDENTITY_EMAIL.fullmatch(email.strip())
    return name_match.group(0) if name_match else email_match.group(0) if email_match else None


def _trailer_ai_label(value):
    identity = TRAILER_IDENTITY.fullmatch(value.strip())
    if identity:
        return _identity_label(identity.group("name"), identity.group("email"))
    return _identity_label(_without_markup(value), "")


def _signature_ai_label(value):
    """Recognize a signature target while leaving ordinary prose and people alone."""
    candidate = _without_markup(value)
    for possible in (
        candidate,
        re.sub(r"\s+(?:for|using|via|with)\s+\S.*$", "", candidate, flags=re.IGNORECASE),
    ):
        label = _identity_label(possible, "")
        if label:
            return label
    # The opening emphasis marker is consumed by ATTRIBUTION_SIGNATURE, so its
    # matching closing marker can remain attached to an otherwise plain target.
    return _identity_label(_without_markup(value.rstrip("*_ ")), "")


def _non_fenced_lines(text):
    """Return numbered Markdown lines, excluding fenced examples and their markers."""
    lines = []
    fence_character = None
    fence_length = 0
    for number, line in enumerate((text or "").splitlines(), 1):
        if fence_character:
            closing = re.match(
                rf"^ {{0,3}}{re.escape(fence_character)}{{{fence_length},}}[ \t]*$",
                line,
            )
            if closing:
                fence_character = None
                fence_length = 0
            continue
        opening = FENCE_START.match(line)
        if opening:
            marker = opening.group("marker")
            fence_character = marker[0]
            fence_length = len(marker)
            continue
        lines.append((number, line))
    return lines


def _signature_at(lines, start):
    """Match one attribution signature, unfolding a short Markdown-wrapped target."""
    if not lines[start][1].strip():
        return None
    parts = []
    previous_number = None
    for end in range(start, min(start + 4, len(lines))):
        number, line = lines[end]
        if previous_number is not None and number != previous_number + 1:
            break
        if end > start and not line.strip():
            break
        previous_number = number
        parts.append(line.strip())
        combined = " ".join(part for part in parts if part)
        signature = ATTRIBUTION_SIGNATURE.match(combined)
        if signature and _signature_ai_label(signature.group("target")):
            return end, combined
    return None


def _metadata_finding(metadata):
    """Classify attribution metadata while ignoring prose-shaped session headings."""
    value = (metadata.group("value") or "").strip()
    if not value:
        return None
    kind = metadata.group("kind").lower()
    if kind == "task":
        return "AI task trailer"
    if re.match(r"https?://\S+$", _without_markup(value), re.IGNORECASE):
        return "AI session trailer"
    token = _without_markup(value).split(maxsplit=1)[0]
    qualifier = (metadata.group("qualifier") or "").lower()
    if qualifier == "id":
        return "AI session trailer"
    if qualifier in ("url", "link") and re.match(r"https?://\S+$", token, re.IGNORECASE):
        return "AI session trailer"
    if OPAQUE_METADATA_ID.fullmatch(token):
        return "AI session trailer"
    return None


def inspect_identity(source, role, name, email):
    """Return one finding when an author/committer identifies an AI persona."""
    identity = f"{name} <{email}>"
    label = _identity_label(name, email)
    if not label:
        return []
    return [Finding(source, f"{role} identity", f"{identity!r} names {label!r}")]


def inspect_text(text, source):
    """Find attribution-shaped lines without rejecting ordinary technical prose."""
    findings = []
    lines = _non_fenced_lines(text)
    index = 0
    while index < len(lines):
        number, line = lines[index]
        trailer = BY_TRAILER.match(line)
        if trailer:
            if _trailer_ai_label(trailer.group("value") or ""):
                findings.append(Finding(
                    f"{source} line {number}",
                    "AI attribution trailer",
                    line.strip(),
                ))
                index += 1
                continue
        metadata = AI_METADATA_TRAILER.match(line)
        metadata_kind = _metadata_finding(metadata) if metadata else None
        if metadata_kind:
            findings.append(Finding(
                f"{source} line {number}",
                metadata_kind,
                line.strip(),
            ))
            index += 1
            continue
        signature = _signature_at(lines, index)
        if signature:
            end, detail = signature
            findings.append(Finding(
                f"{source} line {number}",
                "AI generation signature",
                detail,
            ))
            index = end + 1
            continue
        if SESSION_URL.search(line):
            findings.append(Finding(
                f"{source} line {number}",
                "AI session URL",
                line.strip(),
            ))
        index += 1
    return findings


def _read_commit(repository, commit):
    result = _git(
        repository,
        "show",
        "--no-patch",
        "--format=%H%x00%an%x00%ae%x00%cn%x00%ce%x00%B",
        commit,
    )
    fields = result.stdout.split("\0", 5)
    if len(fields) != 6:
        raise AttributionCheckError(f"could not parse commit metadata for {commit}")
    return fields


def _inspect_commits(repository, commits):
    findings = []
    for commit in commits:
        sha, author_name, author_email, committer_name, committer_email, message = _read_commit(
            repository, commit
        )
        source = f"commit {sha[:12]}"
        findings.extend(inspect_identity(source, "author", author_name, author_email))
        findings.extend(inspect_identity(source, "committer", committer_name, committer_email))
        findings.extend(inspect_text(message, f"{source} message"))
    return findings, len(commits)


def inspect_range(repository, base, head="HEAD"):
    """Return (findings, commit_count) for the diagnostic ``base..head`` range."""
    repository = Path(repository)
    base_commit = _resolve_commit(repository, base, "base")
    head_commit = _resolve_commit(repository, head, "head")
    commits = _git(
        repository,
        "rev-list",
        "--reverse",
        "--topo-order",
        f"{base_commit}..{head_commit}",
    ).stdout.splitlines()
    return _inspect_commits(repository, commits)


def inspect_history(repository, head="HEAD"):
    """Return (findings, commit_count) for every commit reachable from ``head``."""
    repository = Path(repository)
    head_commit = _resolve_commit(repository, head, "head")
    commits = _git(
        repository,
        "rev-list",
        "--reverse",
        "--topo-order",
        head_commit,
    ).stdout.splitlines()
    return _inspect_commits(repository, commits)


def inspect_event(path):
    """Inspect a GitHub event's pull-request title/body, when it has a PR."""
    try:
        with Path(path).open(encoding="utf-8") as handle:
            event = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise AttributionCheckError(f"cannot read GitHub event JSON {path}: {error}") from error
    if not isinstance(event, dict):
        raise AttributionCheckError("GitHub event must be an object")
    pull_request = event.get("pull_request")
    if pull_request is None:
        return []
    if not isinstance(pull_request, dict):
        raise AttributionCheckError("GitHub event pull_request must be an object")
    findings = []
    actor = pull_request.get("user")
    if actor is not None:
        if not isinstance(actor, dict):
            raise AttributionCheckError("GitHub pull_request.user must be an object or null")
        login = actor.get("login")
        if login is not None and not isinstance(login, str):
            raise AttributionCheckError("GitHub pull_request.user.login must be text or null")
        if login and not DEPENDABOT_IDENTITY.fullmatch(login):
            label = _identity_label(login, "")
            if label:
                findings.append(Finding(
                    "pull request actor",
                    "AI actor identity",
                    f"{login!r} names {label!r}",
                ))
    for field in ("title", "body"):
        value = pull_request.get(field)
        if value is None:
            continue
        if not isinstance(value, str):
            raise AttributionCheckError(f"GitHub pull_request.{field} must be text or null")
        findings.extend(inspect_text(value, f"pull request {field}"))
    return findings


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--audit", action="store_true", help="inspect all history reachable from HEAD")
    scope.add_argument("--base", help="inspect only commits in BASE..HEAD (diagnostic mode)")
    parser.add_argument("--head", default="HEAD", help="head commit to inspect (default: HEAD)")
    parser.add_argument(
        "--repository",
        default=".",
        help="Git work tree to inspect (default: current directory)",
    )
    parser.add_argument(
        "--event-path",
        help="GitHub event JSON; defaults to GITHUB_EVENT_PATH when set",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    event_path = args.event_path or os.environ.get("GITHUB_EVENT_PATH")
    try:
        if args.audit:
            findings, commit_count = inspect_history(args.repository, args.head)
            scope = "reachable"
        else:
            findings, commit_count = inspect_range(args.repository, args.base, args.head)
            scope = "new"
        if event_path:
            findings.extend(inspect_event(event_path))
    except AttributionCheckError as error:
        print(f"Attribution check could not run: {error}", file=sys.stderr)
        return 2
    if findings:
        print(
            f"AI attribution is not permitted ({len(findings)} violation(s)):",
            file=sys.stderr,
        )
        for finding in findings:
            print(f"- {finding.diagnostic()}", file=sys.stderr)
        print(
            "Use an accountable human or neutral automation identity and remove AI "
            "attribution/session signatures. Ordinary technical discussion is allowed.",
            file=sys.stderr,
        )
        return 1
    suffix = " and available event metadata" if event_path else ""
    print(f"Attribution check passed: inspected {commit_count} {scope} commit(s){suffix}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

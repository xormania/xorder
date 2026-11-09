"""Reject a shared foundation whose upstream differs from its consumer's pin."""
import argparse
from pathlib import Path
import re

RECORD = Path("/opt/xorder/components/python-foundation/upstream-image")


def identity(reference):
    match = re.fullmatch(r"([^@\s]+)@(sha256:[a-f0-9]{64})", reference)
    if match is None:
        raise ValueError("Python foundation needs an exact upstream image digest reference")
    repository, digest = match.groups()
    if ":" in repository.rsplit("/", 1)[-1]:
        repository = repository.rsplit(":", 1)[0]
    return repository + "@" + digest


def verify(expected, record=RECORD):
    actual = Path(record).read_text().strip()
    if identity(expected) != identity(actual):
        raise ValueError("Python foundation upstream differs from the consuming image's declared base")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("expected")
    arguments = parser.parse_args()
    verify(arguments.expected)


if __name__ == "__main__":
    main()

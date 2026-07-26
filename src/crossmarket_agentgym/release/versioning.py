"""Version and tag normalization for release candidates and stable releases."""

from __future__ import annotations

import re

_PEP440_RELEASE = re.compile(
    r"^(?P<base>\d+\.\d+\.\d+)(?:(?P<kind>rc)(?P<number>[1-9]\d*))?$"
)


def release_label(version: str) -> str:
    """Return the human/tag label for one accepted PEP 440 release version."""
    match = _PEP440_RELEASE.fullmatch(version)
    if match is None:
        raise ValueError(f"unsupported release version: {version!r}")
    base = match.group("base")
    number = match.group("number")
    return base if number is None else f"{base}-rc{number}"


def release_tag(version: str) -> str:
    """Return the required Git tag for one accepted release version."""
    return f"v{release_label(version)}"


def is_release_candidate(version: str) -> bool:
    """Return whether the accepted release version is an rc build."""
    match = _PEP440_RELEASE.fullmatch(version)
    return match is not None and match.group("kind") == "rc"

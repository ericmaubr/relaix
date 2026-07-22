"""Standalone --version / --about handling, no external dependency required."""

from __future__ import annotations

import json
import sys
from importlib.metadata import PackageNotFoundError, metadata, version

DISTRIBUTION = "relaix"
MODULE = "relaix"


def get_version() -> str:
    try:
        return version(DISTRIBUTION)
    except PackageNotFoundError:
        return "0.0.0.dev"


def format_version_line() -> str:
    return f"{DISTRIBUTION} {get_version()}"


def build_about() -> dict[str, object]:
    try:
        meta = metadata(DISTRIBUTION)
        requires_python = meta.get("Requires-Python", "")
    except PackageNotFoundError:
        requires_python = ""

    return {
        "distribution": DISTRIBUTION,
        "version": get_version(),
        "runtime": "python",
        "runtime_version": (
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        ),
        "module": MODULE,
        "requires_python": requires_python,
    }


def handle_version_flags(argv: list[str] | None = None) -> int | None:
    """Handles --version / --about. Returns an exit code if handled, else None."""
    args = argv if argv is not None else sys.argv[1:]
    if "--version" in args or "-V" in args:
        print(format_version_line())
        return 0
    if "--about" in args:
        print(json.dumps(build_about(), ensure_ascii=False))
        return 0
    return None

"""Check the things that only go wrong at release.

Four faults, all of which pass every other gate and all of which have shipped
somewhere.

**The version is in two places.** ``pyproject.toml`` declares it and
``__init__`` reports it, and a release that bumps one leaves a wheel whose
metadata disagrees with what the installed package says its version is. Nothing
notices until somebody tries to reproduce a bug from a version number.

**The dependency pins are exact or they are not pins.** This package fixes its
stack at a known set of versions on purpose. A ``>=`` that creeps into the list
turns a reproducible build into one that depends on the day it was installed.

**The console script has to point at something importable.** ``pyproject``
names an entry point as text, and nothing checks the text resolves until a user
installs the wheel and types the command.

**The README's command table has to name every group.** That table is the
first thing anybody reads and it is the easiest thing in the repository to
leave behind, because adding a group is a code change and the table is not.
A table missing a group is worse than no table: a reader takes it as the list
of what the tool does and never types the command that would have helped them.

**Every command group has to be registered.** The CLI package imports its group
modules for their side effect of attaching to the root, and a new module that
nobody added to that tuple is a set of commands the built wheel does not have.
The tests import the modules directly and pass; only a fresh process going
through the entry point notices.

Named ``check_release`` rather than ``release_check`` because the workflow
gate finds gates by that prefix. It caught this module the first time it was
added under the other name, which is the gate working.

Run as ``python -m mullerbox.tools.check_release``.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

import mullerbox
from mullerbox.cli import main as root

PACKAGE_ROOT = Path(mullerbox.__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
CLI_ROOT = PACKAGE_ROOT / "cli"

# Modules in the cli package that are not command groups.
NOT_A_GROUP = {"__init__", "context", "judging", "main", "parsing", "systemopts"}

README = REPO_ROOT / "README.md"

# The table row shape, which is how the README lists a group.
_ROW = re.compile(r"^\| `([a-z-]+)` \|", re.MULTILINE)


def declared() -> dict[str, object]:
    """The parsed pyproject, or a refusal naming where it should be."""
    if not PYPROJECT.exists():
        raise FileNotFoundError(f"there is no pyproject at {PYPROJECT}")
    with PYPROJECT.open("rb") as handle:
        loaded: dict[str, object] = tomllib.load(handle)
    return loaded


def _project(data: dict[str, object]) -> dict[str, object]:
    project = data.get("project")
    return project if isinstance(project, dict) else {}


def version_problems(data: dict[str, object]) -> list[str]:
    """Whether the declared version and the reported one agree."""
    declared_version = _project(data).get("version")
    if declared_version != mullerbox.__version__:
        return [
            f"pyproject says version {declared_version!r} and the package reports "
            f"{mullerbox.__version__!r}"
        ]
    return []


def pin_problems(data: dict[str, object]) -> list[str]:
    """Every dependency that is not pinned to an exact version."""
    found: list[str] = []
    project = _project(data)
    groups: list[tuple[str, object]] = [("dependencies", project.get("dependencies"))]
    optional = project.get("optional-dependencies")
    if isinstance(optional, dict):
        groups.extend((f"optional {name}", value) for name, value in optional.items())
    for label, entries in groups:
        if not isinstance(entries, list):
            continue
        for entry in entries:
            text = str(entry)
            if not re.match(r"^[A-Za-z0-9._-]+==[0-9][0-9A-Za-z.+-]*$", text):
                found.append(f"{label} carries {text!r}, which is not an exact pin")
    return found


def entry_point_problems(data: dict[str, object]) -> list[str]:
    """Whether the console script resolves to something importable."""
    scripts = _project(data).get("scripts")
    if not isinstance(scripts, dict) or not scripts:
        return ["pyproject declares no console script"]
    found: list[str] = []
    for name, target in scripts.items():
        text = str(target)
        if ":" not in text:
            found.append(f"console script {name!r} is {text!r}, which names no callable")
            continue
        module_path, _, attribute = text.partition(":")
        try:
            module = __import__(module_path, fromlist=[attribute])
        except ImportError as exc:
            found.append(f"console script {name!r} cannot import {module_path}: {exc}")
            continue
        if not callable(getattr(module, attribute, None)):
            found.append(f"console script {name!r} points at {text!r}, which is not callable")
    return found


def registration_problems() -> list[str]:
    """Every command group module that the root does not carry."""
    registered = set(root.commands)
    found: list[str] = []
    for path in sorted(CLI_ROOT.glob("*.py")):
        if path.stem in NOT_A_GROUP:
            continue
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r'@main\.group\("([^"]+)"\)', text):
            name = match.group(1)
            if name not in registered:
                found.append(
                    f"{path.name} defines the {name!r} group and the root does not "
                    "carry it; add the module to _REGISTERED"
                )
    return found


def documented_groups() -> set[str]:
    """Every group named in the README's command table."""
    if not README.exists():
        return set()
    return set(_ROW.findall(README.read_text(encoding="utf-8")))


def readme_problems() -> list[str]:
    """Groups the README does not list, and rows that name no group."""
    if not README.exists():
        return [f"there is no README at {README}"]
    listed = documented_groups()
    registered = set(root.commands) - {"doctor", "init", "migrate", "status"}
    found = [
        f"the README command table does not list the {name!r} group"
        for name in sorted(registered - listed)
    ]
    found.extend(
        f"the README command table lists {name!r}, which is not a command group"
        for name in sorted(listed - registered)
    )
    return found


def problems() -> list[str]:
    """Everything that would only surface at release."""
    try:
        data = declared()
    except FileNotFoundError as exc:
        return [str(exc)]
    return (
        version_problems(data)
        + pin_problems(data)
        + entry_point_problems(data)
        + registration_problems()
        + readme_problems()
    )


def main() -> int:
    """Print every release problem and exit non-zero if there are any."""
    found = problems()
    for line in found:
        print(line)
    if found:
        print(f"\n{len(found)} release problems")
        return 1
    print(
        f"version {mullerbox.__version__}, pins exact, entry point resolves, "
        f"{len(root.commands)} command groups registered and "
        f"{len(documented_groups())} documented"
    )
    return 0


__all__ = [
    "CLI_ROOT",
    "NOT_A_GROUP",
    "PACKAGE_ROOT",
    "PYPROJECT",
    "README",
    "REPO_ROOT",
    "declared",
    "documented_groups",
    "entry_point_problems",
    "main",
    "pin_problems",
    "problems",
    "readme_problems",
    "registration_problems",
    "version_problems",
]


if __name__ == "__main__":
    sys.exit(main())

"""Check that CI actually runs every gate this package ships.

A gate nobody invokes is worse than no gate. It passes locally when somebody
remembers to run it, it never runs on a pull request, and it accumulates a
backlog of violations that surface the day somebody finally wires it up. The
failure is silent in exactly the way the gates exist to prevent, and it has
happened to every project that has more than two of them.

So this walks the ``tools`` package, finds every ``check_*`` module, and reads
the CI workflow looking for each one being invoked. A gate that is not mentioned
fails this gate, which is the only arrangement that does not need somebody to
remember.

It also checks the reverse: the workflow does not invoke a gate that does not
exist, which is what a rename leaves behind.

**The workflow is read as text, not parsed as YAML.** Adding a YAML library to
run one check in CI is a dependency the shipped package would carry for the
benefit of a script that is not part of it. Substring matching over the file is
cruder and it is enough: the thing being looked for is a module path, and a
module path in a YAML file means the same thing wherever it appears.

Run as ``python -m mullerbox.tools.check_workflow``.
"""

from __future__ import annotations

import sys
from pathlib import Path

TOOLS_ROOT = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_ROOT.parent.parent.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"

# Jobs the workflow has to carry whatever the gates are doing.
REQUIRED_STEPS = (
    "ruff check",
    "ruff format --check",
    "mypy",
    "pytest",
)

# Python versions the test matrix has to cover.
REQUIRED_PYTHONS = ("3.12", "3.13")


def gate_modules() -> list[str]:
    """Every check module in the tools package, as an importable path."""
    return sorted(f"mullerbox.tools.{path.stem}" for path in TOOLS_ROOT.glob("check_*.py"))


def workflow_text() -> str:
    """The CI workflow as text, or a refusal naming where it should be."""
    if not WORKFLOW.exists():
        raise FileNotFoundError(f"there is no workflow at {WORKFLOW}")
    return WORKFLOW.read_text(encoding="utf-8")


def problems() -> list[str]:
    """Everything wrong with how CI and the gates line up."""
    try:
        text = workflow_text()
    except FileNotFoundError as exc:
        return [str(exc)]
    found: list[str] = []
    gates = gate_modules()
    for module in gates:
        if module not in text:
            found.append(f"{module} is a gate and CI does not run it")
    for line in text.splitlines():
        stripped = line.strip()
        if "mullerbox.tools." not in stripped:
            continue
        for word in stripped.replace('"', " ").replace("'", " ").split():
            if word.startswith("mullerbox.tools.") and word not in gates:
                found.append(f"CI runs {word}, which is not a gate in this package")
    for step in REQUIRED_STEPS:
        if step not in text:
            found.append(f"CI does not run {step!r}")
    for version in REQUIRED_PYTHONS:
        if version not in text:
            found.append(f"CI does not test on Python {version}")
    return found


def main() -> int:
    """Print every workflow problem and exit non-zero if there are any."""
    found = problems()
    for line in found:
        print(line)
    if found:
        print(f"\n{len(found)} workflow problems")
        return 1
    print(f"CI runs all {len(gate_modules())} gates on {len(REQUIRED_PYTHONS)} versions")
    return 0


if __name__ == "__main__":
    sys.exit(main())

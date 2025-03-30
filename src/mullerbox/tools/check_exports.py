"""Check that every module's ``__all__`` tells the truth.

Three faults, all of which have shipped in packages this size and none of which
any other gate here catches.

**A name in ``__all__`` that is not defined.** Survives lint, survives mypy,
survives every test that does not use a star import, and raises at import time
for the one person who does.

**A public name missing from ``__all__``.** The module exports it in practice
because nothing stops an import, but it is not part of the stated interface, so
it gets renamed in a refactor and something outside breaks. The rule here is
that a module carrying an ``__all__`` has to list every public module level name
it defines, so the list cannot drift behind the module.

**An unsorted ``__all__``.** Not a correctness problem and worth failing on
anyway: an unsorted list makes every future diff to it noisy, and two people
adding a name each get a conflict they would not otherwise have had.

Run as ``python -m mullerbox.tools.check_exports``.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent

# Names a module may define publicly without listing, because they are
# conventions rather than interface.
EXEMPT = {"__version__", "__all__"}


def _module_files() -> list[Path]:
    return sorted(p for p in PACKAGE_ROOT.rglob("*.py") if p.name != "__main__.py")


def _declared(tree: ast.Module) -> list[str] | None:
    """The ``__all__`` list, or None when the module does not declare one."""
    for node in tree.body:
        if not isinstance(node, ast.Assign | ast.AnnAssign):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name) and target.id == "__all__":
                value = node.value
                if value is None or not isinstance(value, ast.List | ast.Tuple):
                    return []
                names: list[str] = []
                for element in value.elts:
                    if isinstance(element, ast.Constant) and isinstance(element.value, str):
                        names.append(element.value)
                return names
    return None


def _public_definitions(tree: ast.Module) -> set[str]:
    """Module level names that do not start with an underscore."""
    found: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            if not node.name.startswith("_"):
                found.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and not target.id.startswith("_"):
                    found.add(target.id)
        elif isinstance(node, ast.AnnAssign):
            target = node.target
            if isinstance(target, ast.Name) and not target.id.startswith("_"):
                found.add(target.id)
    return found - EXEMPT


def problems() -> list[str]:
    """Every export fault in the package, as readable lines."""
    found: list[str] = []
    for path in _module_files():
        relative = path.relative_to(PACKAGE_ROOT.parent)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        declared = _declared(tree)
        if declared is None:
            continue
        defined = _public_definitions(tree)
        for name in declared:
            if name in EXEMPT:
                continue
            if name not in defined and not _is_imported(tree, name):
                found.append(f"{relative}: __all__ names {name!r}, which is not defined")
        missing = sorted(defined - set(declared))
        for name in missing:
            found.append(f"{relative}: {name!r} is public and not in __all__")
        if declared != sorted(declared):
            found.append(f"{relative}: __all__ is not sorted")
    return found


def _is_imported(tree: ast.Module, name: str) -> bool:
    """Whether a name arrived by import, which is how a package re-exports."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if (alias.asname or alias.name) == name:
                    return True
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if (alias.asname or alias.name.split(".")[0]) == name:
                    return True
    return False


def main() -> int:
    found = problems()
    for line in found:
        print(line)
    if found:
        print(f"\n{len(found)} export problems")
        return 1
    print(f"exports are consistent across {len(_module_files())} modules")
    return 0


if __name__ == "__main__":
    sys.exit(main())

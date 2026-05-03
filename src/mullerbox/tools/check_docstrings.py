"""Check that the public surface explains itself.

Not a style gate. The rule is narrow on purpose: every module, and every public
class and function a caller can reach, has a docstring. Nothing here checks
length, grammar or format, because a gate that does turns into a gate people
satisfy with one line of nothing.

What it does catch is the module added in a hurry with no header at all, which
is the case that actually happens and the case that costs the most later,
because a module with no header is a module whose reason for existing was never
written down and cannot be recovered.

**The rule stops where the logic stops.** A function whose body is one or two
statements is its own documentation: ``return self.cents == 0`` under a name
like ``is_zero`` cannot be made clearer by a sentence, and demanding one
produces a package where every real explanation is buried among two hundred
restatements of a name. So the threshold is three statements, and the first
draft of this gate did not have it. It reported 234 names, nearly all of them
accessors, and the honest choice at that point was to narrow the rule rather
than to weaken it afterwards to make the number go down.

Dunder methods are skipped entirely for the same reason, whatever their length.
``__init__`` is the exception among them: it is where construction is validated
and it is skipped only when its class carries a header.

Run as ``python -m mullerbox.tools.check_docstrings``.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent


def _module_files() -> list[Path]:
    return sorted(PACKAGE_ROOT.rglob("*.py"))


def _is_public(name: str) -> bool:
    return not name.startswith("_")


# A body shorter than this explains itself.
TRIVIAL_STATEMENTS = 2


def _body_length(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Statements in a function, not counting its docstring."""
    body = node.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    return len(body)


def _has_docstring(node: ast.AST) -> bool:
    if not isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
        return False
    return bool(ast.get_docstring(node))


def _walk_body(body: list[ast.stmt], path: str, inside: str, class_documented: bool) -> list[str]:
    found: list[str] = []
    for node in body:
        if isinstance(node, ast.ClassDef):
            if not _is_public(node.name):
                continue
            documented = _has_docstring(node)
            if not documented:
                found.append(f"{path}: class {inside}{node.name} has no docstring")
            found.extend(_walk_body(node.body, path, f"{inside}{node.name}.", documented))
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            name = node.name
            if name.startswith("__") and name.endswith("__"):
                if name == "__init__" and not class_documented and _is_public(inside):
                    found.append(
                        f"{path}: {inside}__init__ has no docstring and neither does its class"
                    )
                continue
            if not _is_public(name):
                continue
            if _body_length(node) <= TRIVIAL_STATEMENTS:
                continue
            if not _has_docstring(node):
                found.append(f"{path}: {inside}{name} has no docstring")
    return found


def problems() -> list[str]:
    """Every undocumented public thing in the package."""
    found: list[str] = []
    for path in _module_files():
        relative = str(path.relative_to(PACKAGE_ROOT.parent))
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if not _has_docstring(tree):
            found.append(f"{relative}: the module has no docstring")
        found.extend(_walk_body(tree.body, relative, "", class_documented=True))
    return found


def main() -> int:
    """Print every undocumented public name and exit non-zero if there are any."""
    found = problems()
    for line in found:
        print(line)
    if found:
        print(f"\n{len(found)} undocumented public names")
        return 1
    print(f"every public name across {len(_module_files())} modules is documented")
    return 0


__all__ = [
    "PACKAGE_ROOT",
    "TRIVIAL_STATEMENTS",
    "main",
    "problems",
]


if __name__ == "__main__":
    sys.exit(main())

from __future__ import annotations

import ast

from mullerbox.tools.check_docstrings import (
    TRIVIAL_STATEMENTS,
    _body_length,
    _module_files,
    _walk_body,
    problems,
)


def walk(source: str) -> list[str]:
    tree = ast.parse(source)
    return _walk_body(tree.body, "x.py", "", class_documented=True)


class TestTheGatePassesOnThisPackage:
    def test_every_public_name_is_documented(self) -> None:
        assert problems() == []

    def test_it_actually_looked_at_the_modules(self) -> None:
        assert len(_module_files()) > 40


class TestTheThresholdStopsAtTrivialBodies:
    def test_a_one_line_accessor_needs_nothing(self) -> None:
        assert walk("def is_zero(self):\n    return self.cents == 0") == []

    def test_a_two_line_body_needs_nothing(self) -> None:
        source = "def scaled(self, f):\n    ratio = f\n    return ratio * 2"
        assert walk(source) == []

    def test_a_three_line_body_does(self) -> None:
        source = (
            "def scaled(self, f):\n    ratio = f\n    doubled = ratio * 2\n    return doubled\n"
        )
        assert walk(source) == ["x.py: scaled has no docstring"]

    def test_a_documented_three_line_body_passes(self) -> None:
        source = (
            "def scaled(self, f):\n"
            '    """Scale it."""\n'
            "    ratio = f\n"
            "    doubled = ratio * 2\n"
            "    return doubled\n"
        )
        assert walk(source) == []

    def test_the_docstring_is_not_counted_as_a_statement(self) -> None:
        tree = ast.parse('def f():\n    """Doc."""\n    return 1')
        assert _body_length(tree.body[0]) == 1  # type: ignore[arg-type]

    def test_the_threshold_is_two(self) -> None:
        assert TRIVIAL_STATEMENTS == 2


class TestWhatIsSkipped:
    def test_private_names_are_skipped(self) -> None:
        source = "def _helper(a):\n    b = a\n    c = b\n    return c"
        assert walk(source) == []

    def test_dunder_methods_are_skipped_however_long(self) -> None:
        source = (
            "class A:\n"
            '    """Doc."""\n'
            "    def __str__(self):\n"
            "        a = 1\n"
            "        b = 2\n"
            "        return str(a + b)\n"
        )
        assert walk(source) == []

    def test_an_init_is_covered_by_its_class(self) -> None:
        source = 'class A:\n    """Doc."""\n    def __init__(self):\n        self.a = 1\n'
        assert walk(source) == []

    def test_a_private_class_is_skipped(self) -> None:
        source = "class _A:\n    def go(self):\n        a = 1\n        b = 2\n        return a + b"
        assert walk(source) == []


class TestClasses:
    def test_a_public_class_needs_a_docstring(self) -> None:
        assert walk("class A:\n    pass") == ["x.py: class A has no docstring"]

    def test_a_documented_one_passes(self) -> None:
        assert walk('class A:\n    """Doc."""') == []

    def test_a_method_is_named_with_its_class(self) -> None:
        source = (
            "class A:\n"
            '    """Doc."""\n'
            "    def go(self):\n"
            "        a = 1\n"
            "        b = 2\n"
            "        return a + b\n"
        )
        assert walk(source) == ["x.py: A.go has no docstring"]

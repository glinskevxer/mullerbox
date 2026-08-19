from __future__ import annotations

import ast
from pathlib import Path

import pytest

from mullerbox.tools import check_exports
from mullerbox.tools.check_exports import (
    _declared,
    _is_imported,
    _module_files,
    _public_definitions,
    problems,
)


def parse(source: str) -> ast.Module:
    return ast.parse(source)


class TestTheGatePassesOnThisPackage:
    def test_there_are_no_export_problems(self) -> None:
        assert problems() == []

    def test_it_actually_looked_at_the_modules(self) -> None:
        assert len(_module_files()) > 20


class TestReadingAll:
    def test_a_list_is_read(self) -> None:
        assert _declared(parse('__all__ = ["a", "b"]')) == ["a", "b"]

    def test_a_tuple_is_read(self) -> None:
        assert _declared(parse('__all__ = ("a",)')) == ["a"]

    def test_an_annotated_assignment_is_read(self) -> None:
        assert _declared(parse('__all__: list[str] = ["a"]')) == ["a"]

    def test_a_module_without_one_reads_as_none(self) -> None:
        assert _declared(parse("x = 1")) is None

    def test_an_empty_list_is_not_none(self) -> None:
        assert _declared(parse("__all__: list[str] = []")) == []

    def test_non_string_entries_are_skipped(self) -> None:
        assert _declared(parse("__all__ = [1, 'a']")) == ["a"]


class TestFindingPublicNames:
    def test_classes_and_functions(self) -> None:
        found = _public_definitions(parse("class A: pass\ndef b(): pass"))
        assert found == {"A", "b"}

    def test_underscored_names_are_private(self) -> None:
        found = _public_definitions(parse("class _A: pass\ndef _b(): pass\n_C = 1"))
        assert found == set()

    def test_module_constants(self) -> None:
        assert _public_definitions(parse("LIMIT = 5")) == {"LIMIT"}

    def test_annotated_constants(self) -> None:
        assert _public_definitions(parse("LIMIT: int = 5")) == {"LIMIT"}

    def test_version_is_exempt(self) -> None:
        assert _public_definitions(parse('__version__ = "1"')) == set()

    def test_nested_definitions_do_not_count(self) -> None:
        source = "def outer():\n    def inner(): pass\n    return inner"
        assert _public_definitions(parse(source)) == {"outer"}


class TestImportedNamesCount:
    def test_a_from_import_re_exports(self) -> None:
        assert _is_imported(parse("from x import y"), "y")

    def test_an_aliased_import_re_exports_under_the_alias(self) -> None:
        assert _is_imported(parse("from x import y as z"), "z")
        assert not _is_imported(parse("from x import y as z"), "y")

    def test_a_plain_import_re_exports_the_top_name(self) -> None:
        assert _is_imported(parse("import json"), "json")
        assert _is_imported(parse("import a.b.c"), "a")

    def test_something_never_imported(self) -> None:
        assert not _is_imported(parse("from x import y"), "q")


class TestExemptNames:
    def test_dunder_version_may_be_exported_without_being_a_definition(self) -> None:
        """``__version__`` is stripped from the definitions, so it needs an exemption.

        Without one the top level package fails its own gate: it defines
        ``__version__``, the definition scan drops it as a convention, and the
        entry in ``__all__`` then reads as naming something undefined.
        """
        import mullerbox

        assert "__version__" in mullerbox.__all__
        assert not [line for line in problems() if "__init__.py" in line]


class TestTheParserOnOddSources:
    """The gate reads source with ast, so it meets shapes no module here has.

    Every branch below was written for a file that does not exist in this
    package and so had never been executed. A parser branch that has never run
    is a parser branch that might raise on the day somebody writes the file it
    was for, and the gate raising is the gate not running.
    """

    def declared_in(self, tmp_path: Path, body: str) -> list[str] | None:
        target = tmp_path / "sample.py"
        target.write_text(body, encoding="utf-8")
        return _declared(ast.parse(target.read_text(encoding="utf-8")))

    def test_an_all_that_is_not_a_list_declares_nothing(self, tmp_path: Path) -> None:
        assert self.declared_in(tmp_path, "__all__ = set()\n") == []

    def test_an_annotated_all_with_no_value_declares_nothing(self, tmp_path: Path) -> None:
        assert self.declared_in(tmp_path, "__all__: list[str]\n") == []

    def test_a_tuple_all_is_read(self, tmp_path: Path) -> None:
        assert self.declared_in(tmp_path, '__all__ = ("a", "b")\n') == ["a", "b"]

    def test_a_non_string_entry_is_skipped(self, tmp_path: Path) -> None:
        assert self.declared_in(tmp_path, '__all__ = ["a", 1]\n') == ["a"]

    def test_a_module_with_no_all_reads_as_none(self, tmp_path: Path) -> None:
        assert self.declared_in(tmp_path, "x = 1\n") is None

    def test_an_annotated_all_with_a_value_is_read(self, tmp_path: Path) -> None:
        assert self.declared_in(tmp_path, '__all__: list[str] = ["a"]\n') == ["a"]


class TestTheGateBitesOnAWrittenOutModule:
    def problems_for(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str) -> list[str]:
        package = tmp_path / "pkg"
        package.mkdir()
        (package / "sample.py").write_text(body, encoding="utf-8")
        monkeypatch.setattr(check_exports, "PACKAGE_ROOT", package)
        return check_exports.problems()

    def test_a_name_in_all_that_is_not_defined(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        found = self.problems_for(tmp_path, monkeypatch, '__all__ = ["missing"]\n')
        assert len(found) == 1
        assert found[0].endswith("__all__ names 'missing', which is not defined")

    def test_a_public_name_left_out_of_all(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        body = 'def kept() -> None:\n    """Doc."""\n\n\n__all__ = []\n'
        found = self.problems_for(tmp_path, monkeypatch, body)
        assert len(found) == 1
        assert found[0].endswith("'kept' is public and not in __all__")

    def test_an_unsorted_all(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        body = (
            'def b() -> None:\n    """Doc."""\n\n\n'
            'def a() -> None:\n    """Doc."""\n\n\n'
            '__all__ = ["b", "a"]\n'
        )
        found = self.problems_for(tmp_path, monkeypatch, body)
        assert len(found) == 1
        assert found[0].endswith("__all__ is not sorted")

    def test_a_re_exported_import_is_allowed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        body = 'from decimal import Decimal\n\n__all__ = ["Decimal"]\n'
        assert self.problems_for(tmp_path, monkeypatch, body) == []

    def test_a_module_with_no_all_is_left_alone(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert self.problems_for(tmp_path, monkeypatch, "x = 1\n") == []

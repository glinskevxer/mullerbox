from __future__ import annotations

import ast

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

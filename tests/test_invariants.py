"""Properties that have to hold across the whole package, checked once.

Every module tests its own behaviour. What no module tests is the things that
are true of all of them, and those are exactly the things that rot: a new enum
without a label, a value type somebody made mutable, an exception raised outside
the hierarchy the command layer knows how to print.

Each of these has one obvious way to go wrong and no natural owner to catch it,
which is what makes a sweep worth having rather than a per-module test.
"""

from __future__ import annotations

import dataclasses
import importlib
import pkgutil
from enum import Enum
from typing import Any

import pytest

import mullerbox
from mullerbox.errors import SandError

# Dataclasses that are deliberately mutable, and why.
MUTABLE_BY_DESIGN = {
    "Book",  # holds a live sqlite connection and its own closing
    "Table",  # rows are appended as a report is built
    "Context",  # click fills it in on the root and hands it down
}


def every_module() -> list[Any]:
    """Every module in the package, imported."""
    found = []
    for info in pkgutil.walk_packages(mullerbox.__path__, prefix=f"{mullerbox.__name__}."):
        found.append(importlib.import_module(info.name))
    return found


MODULES = every_module()


def every_member(kind: type) -> list[tuple[str, Any]]:
    """Every public class of a given kind defined anywhere in the package."""
    seen: dict[str, Any] = {}
    for module in MODULES:
        for name in dir(module):
            if name.startswith("_"):
                continue
            value = getattr(module, name)
            is_ours = isinstance(value, type) and issubclass(value, kind)
            if is_ours and value.__module__.startswith("mullerbox"):
                seen[f"{value.__module__}.{name}"] = value
    return sorted(seen.items())


class TestTheModulesAllImport:
    def test_there_are_plenty_of_them(self) -> None:
        assert len(MODULES) > 60

    def test_every_one_has_a_docstring(self) -> None:
        for module in MODULES:
            assert module.__doc__, module.__name__


class TestEveryEnumIsUsable:
    @pytest.mark.parametrize(("name", "enum"), every_member(Enum))
    def test_it_has_members(self, name: str, enum: type[Enum]) -> None:
        assert list(enum), name

    @pytest.mark.parametrize(("name", "enum"), every_member(Enum))
    def test_its_members_are_uniquely_named(self, name: str, enum: type[Enum]) -> None:
        names = [m.name for m in enum]
        assert len(set(names)) == len(names), name

    @pytest.mark.parametrize(("name", "enum"), every_member(Enum))
    def test_it_carries_a_label_if_it_carries_string_values(
        self, name: str, enum: type[Enum]
    ) -> None:
        """A string valued enum is one the shop reads, so it needs a label."""
        if not all(isinstance(m.value, str) for m in enum):
            return
        assert hasattr(enum, "label"), name
        for member in enum:
            assert member.label, f"{name}.{member.name}"


class TestValueTypesAreFrozen:
    def test_every_dataclass_is_frozen_unless_named(self) -> None:
        mutable: list[str] = []
        for name, cls in every_member(object):
            if not dataclasses.is_dataclass(cls):
                continue
            if name.rsplit(".", 1)[1] in MUTABLE_BY_DESIGN:
                continue
            params = getattr(cls, "__dataclass_params__", None)
            if params is not None and not params.frozen:
                mutable.append(name)
        assert mutable == [], mutable

    def test_the_exemptions_are_real_classes(self) -> None:
        found = {
            name.rsplit(".", 1)[1]
            for name, cls in every_member(object)
            if dataclasses.is_dataclass(cls)
        }
        assert found >= MUTABLE_BY_DESIGN


class TestTheErrorHierarchy:
    @pytest.mark.parametrize(("name", "cls"), every_member(Exception))
    def test_every_exception_descends_from_the_base(self, name: str, cls: type[Exception]) -> None:
        """Except click's own, which the command layer raises deliberately."""
        if cls.__module__.endswith("cli.context"):
            return
        assert issubclass(cls, SandError), name

    def test_the_base_is_the_only_root(self) -> None:
        roots = [
            name
            for name, cls in every_member(Exception)
            if not issubclass(cls, SandError) and not cls.__module__.endswith("context")
        ]
        assert roots == []


class TestEveryModuleDeclaresItsSurface:
    def test_all_is_present_wherever_there_is_something_public(self) -> None:
        missing: list[str] = []
        for module in MODULES:
            public = [
                n
                for n in dir(module)
                if not n.startswith("_")
                and getattr(getattr(module, n), "__module__", "") == module.__name__
            ]
            if public and not hasattr(module, "__all__"):
                missing.append(module.__name__)
        assert missing == []

    def test_nothing_in_all_is_missing_from_its_module(self) -> None:
        for module in MODULES:
            for name in getattr(module, "__all__", []):
                assert hasattr(module, name), f"{module.__name__}.{name}"

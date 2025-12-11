from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import mullerbox
from mullerbox.tools.check_release import (
    NOT_A_GROUP,
    declared,
    entry_point_problems,
    pin_problems,
    problems,
    registration_problems,
    version_problems,
)


class TestTheGatePassesOnThisRepository:
    def test_there_are_no_release_problems(self) -> None:
        assert problems() == []

    def test_the_pyproject_is_where_it_should_be(self) -> None:
        assert isinstance(declared(), dict)


class TestVersion:
    def test_the_two_agree(self) -> None:
        assert version_problems(declared()) == []

    def test_a_disagreement_is_caught(self) -> None:
        data: Any = {"project": {"version": "9.9.9"}}
        found = version_problems(data)
        assert len(found) == 1
        assert mullerbox.__version__ in found[0]
        assert "9.9.9" in found[0]


class TestPins:
    def test_every_dependency_is_exact(self) -> None:
        assert pin_problems(declared()) == []

    def test_a_floor_is_caught(self) -> None:
        data: Any = {"project": {"dependencies": ["click>=8.1.8"]}}
        found = pin_problems(data)
        assert len(found) == 1
        assert "not an exact pin" in found[0]

    def test_a_bare_name_is_caught(self) -> None:
        data: Any = {"project": {"dependencies": ["click"]}}
        assert len(pin_problems(data)) == 1

    def test_a_compatible_release_is_caught(self) -> None:
        data: Any = {"project": {"dependencies": ["click~=8.1"]}}
        assert len(pin_problems(data)) == 1

    def test_the_optional_group_is_checked_too(self) -> None:
        data: Any = {
            "project": {
                "dependencies": ["click==8.1.8"],
                "optional-dependencies": {"dev": ["pytest>=8"]},
            }
        }
        found = pin_problems(data)
        assert len(found) == 1
        assert "optional dev" in found[0]

    def test_an_exact_pin_passes(self) -> None:
        data: Any = {"project": {"dependencies": ["click==8.1.8"]}}
        assert pin_problems(data) == []


class TestEntryPoint:
    def test_the_console_script_resolves(self) -> None:
        assert entry_point_problems(declared()) == []

    def test_no_script_at_all_is_caught(self) -> None:
        data: Any = {"project": {}}
        assert entry_point_problems(data) == ["pyproject declares no console script"]

    def test_a_target_with_no_callable_is_caught(self) -> None:
        data: Any = {"project": {"scripts": {"mullerbox": "mullerbox.cli"}}}
        found = entry_point_problems(data)
        assert "names no callable" in found[0]

    def test_an_unimportable_module_is_caught(self) -> None:
        data: Any = {"project": {"scripts": {"mullerbox": "nothing.here:main"}}}
        found = entry_point_problems(data)
        assert "cannot import" in found[0]

    def test_a_missing_attribute_is_caught(self) -> None:
        data: Any = {"project": {"scripts": {"mullerbox": "mullerbox.cli:absent"}}}
        found = entry_point_problems(data)
        assert "is not callable" in found[0]


class TestRegistration:
    def test_every_group_is_on_the_root(self) -> None:
        assert registration_problems() == []

    def test_the_non_group_modules_are_named(self) -> None:
        assert {"context", "main", "parsing"} <= NOT_A_GROUP

    def test_it_would_catch_an_unregistered_group(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        import mullerbox.tools.check_release as module

        stray = tmp_path / "cli"
        stray.mkdir()
        (stray / "stray.py").write_text(
            '@main.group("stray")\ndef stray() -> None:\n    pass\n', encoding="utf-8"
        )
        monkeypatch.setattr(module, "CLI_ROOT", stray)
        found = module.registration_problems()
        assert len(found) == 1
        assert "the root does not carry it" in found[0]
        assert "_REGISTERED" in found[0]

    def test_a_missing_pyproject_is_reported_rather_than_raised(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        import mullerbox.tools.check_release as module

        monkeypatch.setattr(module, "PYPROJECT", tmp_path / "nothing.toml")
        found = module.problems()
        assert len(found) == 1
        assert "there is no pyproject at" in found[0]

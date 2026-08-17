from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import mullerbox
from mullerbox.cli import main as root
from mullerbox.tools import check_release
from mullerbox.tools.check_release import (
    NOT_A_GROUP,
    declared,
    documented_groups,
    entry_point_problems,
    pin_problems,
    problems,
    readme_problems,
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


class TestTheReadmeTable:
    def test_it_lists_every_command_group(self) -> None:
        assert readme_problems() == []

    def test_there_is_a_table_to_check(self) -> None:
        assert len(documented_groups()) >= 15

    def test_every_documented_group_answers_help(self) -> None:
        for name in documented_groups():
            assert name in root.commands, name

    def test_a_group_left_out_of_the_table_is_caught(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """The positive control, on a README with one row removed."""
        text = check_release.README.read_text(encoding="utf-8")
        thin = tmp_path / "README.md"
        thin.write_text(
            "\n".join(line for line in text.splitlines() if not line.startswith("| `system` |")),
            encoding="utf-8",
        )
        monkeypatch.setattr(check_release, "README", thin)
        found = readme_problems()
        assert found == ["the README command table does not list the 'system' group"]

    def test_a_row_naming_no_group_is_caught_too(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        text = check_release.README.read_text(encoding="utf-8")
        grown = tmp_path / "README.md"
        grown.write_text(text + "\n| `sweepings` | not a thing |\n", encoding="utf-8")
        monkeypatch.setattr(check_release, "README", grown)
        found = readme_problems()
        assert found == ["the README command table lists 'sweepings', which is not a command group"]

    def test_a_missing_readme_is_reported_rather_than_raised(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(check_release, "README", tmp_path / "nothing.md")
        found = readme_problems()
        assert len(found) == 1
        assert "there is no README at" in found[0]

    def test_and_the_group_list_comes_back_empty(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(check_release, "README", tmp_path / "nothing.md")
        assert documented_groups() == set()

    def test_the_helper_modules_are_not_mistaken_for_groups(self) -> None:
        assert "judging" in check_release.NOT_A_GROUP
        assert "systemopts" in check_release.NOT_A_GROUP

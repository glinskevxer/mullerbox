"""Properties that have to hold of every command, checked once.

Each command module tests what its own commands do. What nobody tests is the
shape of the surface as a whole, and that is where a command line goes wrong:
one command whose help is a blank line, one option with no description, one
group nobody registered so it exists in the tests and not in the wheel.

None of those breaks a test. All of them are the first thing a person meets.
"""

from __future__ import annotations

from pathlib import Path

import click
import pytest

from mullerbox.cli.main import main
from tests.cli.helpers import initialised, run

Entry = tuple[tuple[str, ...], click.Command]


def walk(group: click.Group, prefix: tuple[str, ...] = ()) -> list[Entry]:
    """Every command in the tree, as its path and the command itself."""
    found: list[Entry] = []
    for name, command in sorted(group.commands.items()):
        path = (*prefix, name)
        found.append((path, command))
        if isinstance(command, click.Group):
            found.extend(walk(command, path))
    return found


EVERY = walk(main)
LEAVES = [(path, cmd) for path, cmd in EVERY if not isinstance(cmd, click.Group)]
GROUPS = [(path, cmd) for path, cmd in EVERY if isinstance(cmd, click.Group)]


class TestTheTreeIsSubstantial:
    def test_there_are_plenty_of_groups(self) -> None:
        assert len(GROUPS) >= 15

    def test_there_are_plenty_of_commands(self) -> None:
        assert len(LEAVES) >= 45

    def test_no_group_is_empty(self) -> None:
        for path, group in GROUPS:
            assert group.commands, " ".join(path)


class TestEveryCommandExplainsItself:
    @pytest.mark.parametrize(
        ("path", "command"), LEAVES, ids=lambda x: " ".join(x) if isinstance(x, tuple) else ""
    )
    def test_it_has_help_text(self, path: tuple[str, ...], command: click.Command) -> None:
        assert command.help or command.short_help, " ".join(path)

    @pytest.mark.parametrize(
        ("path", "group"), GROUPS, ids=lambda x: " ".join(x) if isinstance(x, tuple) else ""
    )
    def test_every_group_has_help_text(self, path: tuple[str, ...], group: click.Group) -> None:
        assert group.help or group.short_help, " ".join(path)

    def test_the_help_starts_with_a_sentence(self) -> None:
        thin = []
        for path, command in LEAVES:
            text = (command.help or command.short_help or "").strip()
            if len(text.split()) < 4:
                thin.append(" ".join(path))
        assert thin == []


class TestEveryOptionExplainsItself:
    def test_no_option_is_undocumented(self) -> None:
        missing: list[str] = []
        for path, command in LEAVES:
            for param in command.params:
                if not isinstance(param, click.Option):
                    continue
                if param.name in {"help"}:
                    continue
                if not param.help:
                    missing.append(f"{' '.join(path)} --{param.name}")
        assert missing == []

    def test_required_options_are_not_also_defaulted(self) -> None:
        """A required option with a default is one of the two by mistake."""
        confused: list[str] = []
        for path, command in LEAVES:
            for param in command.params:
                required = isinstance(param, click.Option) and param.required
                if required and param.default is not None:
                    confused.append(f"{' '.join(path)} --{param.name}")
        assert confused == []


class TestTheTreeIsReachable:
    def test_every_group_answers_help_without_a_book(self, tmp_path: Path) -> None:
        target = tmp_path / "nothing.sqlite3"
        for path, _ in GROUPS:
            result = run(*path, "--help", book=target)
            assert result.exit_code == 0, " ".join(path)

    def test_help_creates_no_book(self, tmp_path: Path) -> None:
        target = tmp_path / "nothing.sqlite3"
        for path, _ in GROUPS:
            run(*path, "--help", book=target)
        assert not target.exists()

    def test_every_command_answers_help(self, tmp_path: Path) -> None:
        book = initialised(tmp_path)
        for path, _ in LEAVES:
            result = run(*path, "--help", book=book)
            assert result.exit_code == 0, " ".join(path)

    def test_the_root_lists_every_group(self, tmp_path: Path) -> None:
        result = run("--help", book=tmp_path / "nothing.sqlite3")
        for path, _ in GROUPS:
            assert path[0] in result.output


class TestNamesAreConsistent:
    def test_no_command_name_uses_an_underscore(self) -> None:
        """The shell convention is a hyphen and mixing the two is a guess."""
        bad = [" ".join(p) for p, _ in EVERY if "_" in p[-1]]
        assert bad == []

    def test_no_option_name_uses_an_underscore_on_the_command_line(self) -> None:
        bad: list[str] = []
        for path, command in LEAVES:
            for param in command.params:
                if not isinstance(param, click.Option):
                    continue
                for opt in param.opts:
                    if opt.startswith("--") and "_" in opt:
                        bad.append(f"{' '.join(path)} {opt}")
        assert bad == []

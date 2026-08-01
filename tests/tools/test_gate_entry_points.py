"""The gates as CI runs them, which is through ``main`` and an exit code.

Every gate has its own test module covering what it finds. None of them covered
the part CI actually depends on: that ``main`` prints the findings and returns
the right code. A gate whose ``problems`` list is perfect and whose ``main``
returns zero regardless is a gate that passes on a broken repository, and it
looks identical in the workflow log to one that works.

So this exercises each entry point twice, once on the real package and once with
its finder stubbed to report something. The second half is the positive control:
without it a green run proves only that nothing raised.
"""

from __future__ import annotations

from collections.abc import Callable
from unittest import mock

import pytest

from mullerbox.tools import (
    check_docstrings,
    check_exports,
    check_migrations,
    check_release,
    check_workflow,
)

GATES = (
    check_docstrings,
    check_exports,
    check_migrations,
    check_release,
    check_workflow,
)


def named(gate: object) -> str:
    return str(getattr(gate, "__name__", gate)).rsplit(".", 1)[-1]


@pytest.mark.parametrize("gate", GATES, ids=named)
class TestEveryGateEntryPoint:
    def test_it_passes_on_this_package(
        self, gate: object, capsys: pytest.CaptureFixture[str]
    ) -> None:
        run: Callable[[], int] = gate.main  # type: ignore[attr-defined]
        assert run() == 0
        assert capsys.readouterr().out.strip() != ""

    def test_it_fails_and_says_so_when_something_is_found(
        self, gate: object, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with mock.patch.object(gate, "problems", return_value=["a made up finding"]):
            code: int = gate.main()  # type: ignore[attr-defined]
        printed = capsys.readouterr().out
        assert code == 1
        assert "a made up finding" in printed

    def test_the_failure_line_counts_what_it_found(
        self, gate: object, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with mock.patch.object(gate, "problems", return_value=["one", "two", "three"]):
            gate.main()  # type: ignore[attr-defined]
        assert "3 " in capsys.readouterr().out

    def test_it_prints_every_finding_and_not_just_the_first(
        self, gate: object, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with mock.patch.object(gate, "problems", return_value=["first", "second"]):
            gate.main()  # type: ignore[attr-defined]
        printed = capsys.readouterr().out
        assert "first" in printed
        assert "second" in printed

    def test_it_is_a_module_the_workflow_gate_knows_about(self, gate: object) -> None:
        assert f"mullerbox.tools.{named(gate)}" in check_workflow.gate_modules()


class TestTheWorkflowGateOnAThinFile:
    def thin(self, tmp_path: object, lines: list[str]) -> object:
        target = tmp_path / "ci.yml"  # type: ignore[operator]
        body = [f"run: python -m {m}" for m in check_workflow.gate_modules()] + lines
        target.write_text("\n".join(body), encoding="utf-8")
        return target

    def test_a_missing_step_is_named(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: object
    ) -> None:
        target = self.thin(tmp_path, ["python-version: 3.12", "python-version: 3.13"])
        monkeypatch.setattr(check_workflow, "WORKFLOW", target)
        found = check_workflow.problems()
        assert len(found) == len(check_workflow.REQUIRED_STEPS)
        assert all("CI does not run" in line for line in found)

    def test_a_missing_python_version_is_named(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: object
    ) -> None:
        target = self.thin(
            tmp_path,
            [
                "run: ruff check .",
                "run: ruff format --check .",
                "run: mypy",
                "run: pytest -q",
                "python-version: 3.12",
            ],
        )
        monkeypatch.setattr(check_workflow, "WORKFLOW", target)
        found = check_workflow.problems()
        assert found == ["CI does not test on Python 3.13"]

    def test_a_complete_thin_file_passes(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: object
    ) -> None:
        target = self.thin(
            tmp_path,
            [
                "run: ruff check .",
                "run: ruff format --check .",
                "run: mypy",
                "run: pytest -q",
                "python-version: 3.12",
                "python-version: 3.13",
            ],
        )
        monkeypatch.setattr(check_workflow, "WORKFLOW", target)
        assert check_workflow.problems() == []

    def test_the_real_workflow_is_not_that_thin(self) -> None:
        text = check_workflow.workflow_text()
        assert "--cov-fail-under" in text
        assert len(text.splitlines()) > 40

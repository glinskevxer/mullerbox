from __future__ import annotations

from pathlib import Path

import pytest

from mullerbox.tools.check_workflow import (
    REQUIRED_PYTHONS,
    REQUIRED_STEPS,
    WORKFLOW,
    gate_modules,
    problems,
    workflow_text,
)


class TestTheGatePassesOnThisRepository:
    def test_ci_runs_every_gate(self) -> None:
        assert problems() == []

    def test_there_are_gates_to_run(self) -> None:
        assert len(gate_modules()) >= 4

    def test_the_workflow_is_where_it_should_be(self) -> None:
        assert WORKFLOW.exists()
        assert WORKFLOW.name == "ci.yml"


class TestEveryGateIsNamed:
    @pytest.mark.parametrize("module", gate_modules())
    def test_the_workflow_mentions_it(self, module: str) -> None:
        assert module in workflow_text()

    def test_this_gate_checks_itself(self) -> None:
        assert "mullerbox.tools.check_workflow" in gate_modules()

    def test_the_gate_list_comes_from_the_files(self) -> None:
        names = {m.rsplit(".", 1)[1] for m in gate_modules()}
        folder = Path(__file__).resolve()
        assert all(name.startswith("check_") for name in names)
        assert folder.exists()


class TestTheRequiredSteps:
    @pytest.mark.parametrize("step", REQUIRED_STEPS)
    def test_ci_runs_it(self, step: str) -> None:
        assert step in workflow_text()

    @pytest.mark.parametrize("version", REQUIRED_PYTHONS)
    def test_ci_tests_on_it(self, version: str) -> None:
        assert version in workflow_text()

    def test_the_coverage_floor_is_enforced_in_ci(self) -> None:
        assert "--cov-fail-under" in workflow_text()

    def test_the_wheel_is_built_and_installed(self) -> None:
        text = workflow_text()
        assert "python -m build --wheel" in text
        assert "pip install dist/*.whl" in text


class TestTheReverseCheck:
    def test_ci_names_no_gate_that_does_not_exist(self) -> None:
        text = workflow_text()
        gates = set(gate_modules())
        for line in text.splitlines():
            for word in line.replace('"', " ").replace("'", " ").split():
                if word.startswith("mullerbox.tools."):
                    assert word in gates, word

    def test_a_missing_workflow_is_reported_rather_than_raised(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        import mullerbox.tools.check_workflow as module

        monkeypatch.setattr(module, "WORKFLOW", tmp_path / "nothing.yml")
        found = module.problems()
        assert len(found) == 1
        assert "there is no workflow at" in found[0]

    def test_reading_a_missing_workflow_raises(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        import mullerbox.tools.check_workflow as module

        monkeypatch.setattr(module, "WORKFLOW", tmp_path / "nothing.yml")
        with pytest.raises(FileNotFoundError, match="there is no workflow"):
            module.workflow_text()


class TestItWouldCatchTheRealFailure:
    def test_a_gate_missing_from_the_workflow_is_caught(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        import mullerbox.tools.check_workflow as module

        thin = tmp_path / "ci.yml"
        thin.write_text(
            "\n".join(
                [
                    "run: ruff check .",
                    "run: ruff format --check .",
                    "run: mypy",
                    "run: pytest -q",
                    "python-version: 3.12",
                    "python-version: 3.13",
                ]
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(module, "WORKFLOW", thin)
        found = module.problems()
        assert len(found) == len(gate_modules())
        assert all("CI does not run it" in line for line in found)

    def test_a_renamed_gate_left_in_the_workflow_is_caught(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        import mullerbox.tools.check_workflow as module

        stale = tmp_path / "ci.yml"
        body = [f"run: python -m {m}" for m in gate_modules()]
        body.append("run: python -m mullerbox.tools.check_gone")
        body.extend(
            [
                "run: ruff check .",
                "run: ruff format --check .",
                "run: mypy",
                "run: pytest -q",
                "python-version: 3.12",
                "python-version: 3.13",
            ]
        )
        stale.write_text("\n".join(body), encoding="utf-8")
        monkeypatch.setattr(module, "WORKFLOW", stale)
        found = module.problems()
        assert any("check_gone" in line for line in found)
        assert any("is not a gate in this package" in line for line in found)

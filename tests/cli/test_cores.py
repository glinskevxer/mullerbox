from __future__ import annotations

from pathlib import Path

import pytest

from mullerbox.cli.context import EXIT_RULE
from tests.cli.helpers import initialised, run

MIXED = "2025-11-24T07:30:00"

SYSTEM = [
    "--resin",
    "1.2",
    "--catalyst",
    "0.06",
    "--bench-life",
    "300",
    "--strip",
    "120",
    "--cure",
    "900",
    "--floor",
    "180",
]


def at(seconds: int) -> str:
    from datetime import datetime, timedelta

    return (datetime.fromisoformat(MIXED) + timedelta(seconds=seconds)).isoformat()


@pytest.fixture
def book(tmp_path: Path) -> Path:
    target = initialised(tmp_path)
    assert (
        run("core", "add-system", "pep", "phenolic urethane", *SYSTEM, book=target).exit_code == 0
    )
    assert (
        run(
            "core", "mix", "CB-1", "--system", "pep", "--at", MIXED, "--charged", "400", book=target
        ).exit_code
        == 0
    )
    return target


class TestSystems:
    def test_adding_one(self, tmp_path: Path) -> None:
        target = initialised(tmp_path)
        result = run("core", "add-system", "pep", "phenolic urethane", *SYSTEM, book=target)
        assert result.exit_code == 0
        assert "bench life 5:00" in result.output

    def test_listing(self, book: Path) -> None:
        result = run("core", "systems", book=book)
        assert "pep" in result.output
        assert "5:00" in result.output

    def test_an_empty_book_says_so(self, tmp_path: Path) -> None:
        target = initialised(tmp_path)
        assert "no binder systems" in run("core", "systems", book=target).output

    def test_an_unknown_binder_lists_the_real_ones(self, tmp_path: Path) -> None:
        target = initialised(tmp_path)
        result = run("core", "add-system", "x", "epoxy", *SYSTEM, book=target)
        assert result.exit_code == EXIT_RULE
        assert "is not a binder" in result.output

    def test_a_strip_past_bench_life_is_refused(self, tmp_path: Path) -> None:
        target = initialised(tmp_path)
        args = [
            "--resin",
            "1.2",
            "--catalyst",
            "0.06",
            "--bench-life",
            "100",
            "--strip",
            "120",
            "--cure",
            "900",
            "--floor",
            "180",
        ]
        result = run("core", "add-system", "bad", "furan", *args, book=target)
        assert result.exit_code == EXIT_RULE
        assert "dies before the core can be drawn" in result.output


class TestTheClockRefusesTheDraw:
    def test_blowing_inside_bench_life_works(self, book: Path) -> None:
        result = run("core", "blow", "CB-1", "--mass", "100", "--at", at(60), book=book)
        assert result.exit_code == 0
        assert "300.00 lb left" in result.output

    def test_blowing_past_bench_life_is_refused_with_the_age(self, book: Path) -> None:
        result = run("core", "blow", "CB-1", "--mass", "100", "--at", at(400), book=book)
        assert result.exit_code == EXIT_RULE
        assert "past the 5:00 bench life" in result.output

    def test_blowing_more_than_is_left_is_refused(self, book: Path) -> None:
        result = run("core", "blow", "CB-1", "--mass", "500", "--at", at(60), book=book)
        assert result.exit_code == EXIT_RULE
        assert "has 400.00 lb left" in result.output

    def test_the_draw_is_written_back(self, book: Path) -> None:
        run("core", "blow", "CB-1", "--mass", "100", "--at", at(60), book=book)
        result = run("core", "blow", "CB-1", "--mass", "100", "--at", at(90), book=book)
        assert "200.00 lb left" in result.output

    def test_a_bad_moment_names_the_format(self, book: Path) -> None:
        result = run("core", "blow", "CB-1", "--mass", "100", "--at", "yesterday", book=book)
        assert result.exit_code == EXIT_RULE
        assert "yyyy-mm-ddThh:mm:ss" in result.output


class TestJudging:
    def test_a_batch_with_no_specimens(self, book: Path) -> None:
        result = run("core", "judge", "CB-1", book=book)
        assert result.exit_code == 0
        assert "no specimens broken" in result.output

    def test_a_good_batch_passes(self, book: Path) -> None:
        run("core", "break", "CB-1", "T-1", "200", "--at", at(900), book=book)
        run("core", "break", "CB-1", "T-2", "220", "--at", at(900), book=book)
        result = run("core", "judge", "CB-1", book=book)
        assert "passes" in result.output
        assert "210.0 psi" in result.output

    def test_one_under_the_floor_fails_the_batch(self, book: Path) -> None:
        run("core", "break", "CB-1", "T-1", "200", "--at", at(900), book=book)
        run("core", "break", "CB-1", "T-2", "150", "--at", at(900), book=book)
        result = run("core", "judge", "CB-1", book=book)
        assert "fails" in result.output
        assert "T-2" in result.output

    def test_specimens_off_cure_are_named_as_left_out(self, book: Path) -> None:
        run("core", "break", "CB-1", "T-1", "200", "--at", at(900), book=book)
        run("core", "break", "CB-1", "T-2", "10", "--at", at(200), book=book)
        result = run("core", "judge", "CB-1", book=book)
        assert "left out of the judgement" in result.output
        assert "T-2" in result.output

    def test_breaking_off_cure_is_flagged_at_entry(self, book: Path) -> None:
        result = run("core", "break", "CB-1", "T-9", "10", "--at", at(200), book=book)
        assert "AWAY FROM FULL CURE" in result.output

    def test_a_batch_with_nothing_at_cure_cannot_be_judged(self, book: Path) -> None:
        run("core", "break", "CB-1", "T-1", "10", "--at", at(200), book=book)
        result = run("core", "judge", "CB-1", book=book)
        assert result.exit_code == EXIT_RULE
        assert "cannot be judged" in result.output

    def test_the_same_specimen_twice_is_refused(self, book: Path) -> None:
        run("core", "break", "CB-1", "T-1", "200", "--at", at(900), book=book)
        result = run("core", "break", "CB-1", "T-1", "200", "--at", at(900), book=book)
        assert result.exit_code == EXIT_RULE

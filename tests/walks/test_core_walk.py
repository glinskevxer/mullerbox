"""A core room shift, driven through the command line.

The core room's failures are all about time, and time is the one thing a unit
test of a single module cannot get wrong convincingly: every module here takes
the moment as an argument, so each one passes its own tests with any clock at
all. What this walk checks is that the moments line up across the commands, that
a batch mixed at half past seven is the same batch at half past eight, and that
the refusals fire in the order the room actually meets them.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from mullerbox.cli.context import EXIT_RULE
from tests.cli.helpers import initialised, run

MIXED = datetime(2026, 1, 12, 7, 30, 0)

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
    return (MIXED + timedelta(seconds=seconds)).isoformat()


@pytest.fixture
def room(tmp_path: Path) -> Path:
    book = initialised(tmp_path)
    assert run("core", "add-system", "pep", "phenolic urethane", *SYSTEM, book=book).exit_code == 0
    return book


class TestAWholeCoreShift:
    def test_mix_blow_break_judge(self, room: Path) -> None:
        book = room

        mixed = run(
            "core",
            "mix",
            "CB-1",
            "--system",
            "pep",
            "--at",
            MIXED.isoformat(),
            "--charged",
            "400",
            book=book,
        )
        assert mixed.exit_code == 0
        assert "core batch CB-1" in mixed.output

        # Two boxes blown inside bench life, drawing the batch down.
        first = run("core", "blow", "CB-1", "--mass", "100", "--at", at(60), book=book)
        assert first.exit_code == 0
        assert "300.00 lb left" in first.output
        second = run("core", "blow", "CB-1", "--mass", "150", "--at", at(180), book=book)
        assert "150.00 lb left" in second.output

        # Specimens broken at full cure, which is fifteen minutes on this binder.
        for specimen, psi in (("T-1", "205"), ("T-2", "215")):
            broken = run("core", "break", "CB-1", specimen, psi, "--at", at(900), book=book)
            assert broken.exit_code == 0
            assert "at full cure" in broken.output

        judged = run("core", "judge", "CB-1", book=book)
        assert judged.exit_code == 0
        assert "passes" in judged.output
        assert "210.0 psi" in judged.output

    def test_the_batch_is_the_same_batch_an_hour_later(self, room: Path) -> None:
        book = room
        run(
            "core",
            "mix",
            "CB-2",
            "--system",
            "pep",
            "--at",
            MIXED.isoformat(),
            "--charged",
            "400",
            book=book,
        )
        run("core", "blow", "CB-2", "--mass", "100", "--at", at(60), book=book)
        # An hour on, the draw is still recorded and the age is measured from
        # the original mix rather than from the last command.
        late = run("core", "blow", "CB-2", "--mass", "100", "--at", at(120), book=book)
        assert "200.00 lb left" in late.output


class TestTheRefusalsFireInTheOrderTheRoomMeetsThem:
    def test_bench_life_stops_the_draw(self, room: Path) -> None:
        book = room
        run(
            "core",
            "mix",
            "CB-3",
            "--system",
            "pep",
            "--at",
            MIXED.isoformat(),
            "--charged",
            "400",
            book=book,
        )
        result = run("core", "blow", "CB-3", "--mass", "100", "--at", at(400), book=book)
        assert result.exit_code == EXIT_RULE
        assert "past the 5:00 bench life" in result.output

    def test_running_out_stops_the_draw_too(self, room: Path) -> None:
        book = room
        run(
            "core",
            "mix",
            "CB-4",
            "--system",
            "pep",
            "--at",
            MIXED.isoformat(),
            "--charged",
            "200",
            book=book,
        )
        run("core", "blow", "CB-4", "--mass", "150", "--at", at(60), book=book)
        result = run("core", "blow", "CB-4", "--mass", "100", "--at", at(90), book=book)
        assert result.exit_code == EXIT_RULE
        assert "has 50.00 lb left" in result.output

    def test_a_specimen_broken_early_does_not_judge_the_batch(self, room: Path) -> None:
        book = room
        run(
            "core",
            "mix",
            "CB-5",
            "--system",
            "pep",
            "--at",
            MIXED.isoformat(),
            "--charged",
            "400",
            book=book,
        )
        early = run("core", "break", "CB-5", "T-9", "40", "--at", at(200), book=book)
        assert "AWAY FROM FULL CURE" in early.output
        result = run("core", "judge", "CB-5", book=book)
        assert result.exit_code == EXIT_RULE
        assert "cannot be judged" in result.output

    def test_a_good_specimen_rescues_the_batch_and_names_the_one_left_out(self, room: Path) -> None:
        book = room
        run(
            "core",
            "mix",
            "CB-6",
            "--system",
            "pep",
            "--at",
            MIXED.isoformat(),
            "--charged",
            "400",
            book=book,
        )
        run("core", "break", "CB-6", "T-9", "40", "--at", at(200), book=book)
        run("core", "break", "CB-6", "T-10", "210", "--at", at(900), book=book)
        result = run("core", "judge", "CB-6", book=book)
        assert result.exit_code == 0
        assert "passes" in result.output
        assert "T-9" in result.output
        assert "left out of the judgement" in result.output


class TestTheSystemGovernsTheClock:
    def test_a_slower_binder_moves_every_boundary(self, room: Path) -> None:
        book = room
        slow = [
            "--resin",
            "1.5",
            "--catalyst",
            "0.08",
            "--bench-life",
            "1200",
            "--strip",
            "600",
            "--cure",
            "1800",
            "--floor",
            "150",
        ]
        assert run("core", "add-system", "furan slow", "furan", *slow, book=book).exit_code == 0
        run(
            "core",
            "mix",
            "CB-7",
            "--system",
            "furan slow",
            "--at",
            MIXED.isoformat(),
            "--charged",
            "400",
            book=book,
        )

        # A draw that would be past bench life on the fast binder is fine here.
        result = run("core", "blow", "CB-7", "--mass", "100", "--at", at(400), book=book)
        assert result.exit_code == 0

        # And full cure is half an hour rather than fifteen minutes.
        early = run("core", "break", "CB-7", "T-11", "160", "--at", at(900), book=book)
        assert "AWAY FROM FULL CURE" in early.output
        on_time = run("core", "break", "CB-7", "T-12", "160", "--at", at(1800), book=book)
        assert "at full cure" in on_time.output

    def test_the_two_systems_are_listed_with_their_own_times(self, room: Path) -> None:
        book = room
        slow = [
            "--resin",
            "1.5",
            "--catalyst",
            "0.08",
            "--bench-life",
            "1200",
            "--strip",
            "600",
            "--cure",
            "1800",
            "--floor",
            "150",
        ]
        run("core", "add-system", "furan slow", "furan", *slow, book=book)
        result = run("core", "systems", book=book)
        assert "5:00" in result.output
        assert "20:00" in result.output

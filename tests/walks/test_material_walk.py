"""A delivery arriving and being accepted or held, through the command line.

The material path has a shape the other paths do not: it is a gate rather than a
calculation. Sand cannot go into the system until somebody's name is on a
release, and the whole point of the commands is that the gate cannot be walked
round. This walk drives it from the wrong end as well as the right one, because
the interesting property is what the commands refuse.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mullerbox.cli.context import EXIT_RULE
from tests.cli.helpers import initialised, run

DELIVERED = "2026-02-16"


@pytest.fixture
def yard(tmp_path: Path) -> Path:
    return initialised(tmp_path)


def book_in(yard: Path, lot: str = "L-1", **claims: str) -> None:
    args = [
        "material",
        "book-in",
        lot,
        "new sand",
        "48000",
        "--on",
        DELIVERED,
        "--certificate",
        f"COA-{lot}",
    ]
    for flag, value in claims.items():
        args.extend([f"--{flag}", value])
    assert run(*args, book=yard).exit_code == 0


class TestALotThatChecksOut:
    def test_book_in_verify_test_release(self, yard: Path) -> None:
        book_in(yard, gfn="58.0", clay="0.30")

        held = run("material", "held", book=yard)
        assert "L-1" in held.output
        assert "delivered" in held.output

        checked = run("material", "verify", "L-1", "--gfn", "58.5", "--clay", "0.32", book=yard)
        assert checked.exit_code == 0
        assert "fit to release" in checked.output

        # Verifying is not releasing.
        assert "L-1" in run("material", "held", book=yard).output

        assert run("material", "test", "L-1", book=yard).exit_code == 0
        released = run("material", "release", "L-1", "--by", "j.mercer", book=yard)
        assert released.exit_code == 0
        assert "released by j.mercer" in released.output
        assert "nothing held" in run("material", "held", book=yard).output


class TestALotThatDoesNot:
    def test_a_discrepancy_leads_to_a_quarantine(self, yard: Path) -> None:
        book_in(yard, gfn="58.0")
        checked = run("material", "verify", "L-1", "--gfn", "72.0", book=yard)
        assert "quarantine" in checked.output
        assert "certificate says 58.0" in checked.output

        held = run("material", "quarantine", "L-1", "--why", "runs coarse", book=yard)
        assert held.exit_code == 0
        listing = run("material", "held", book=yard)
        assert "quarantined" in listing.output
        assert "runs coarse" in listing.output

    def test_a_quarantined_lot_cannot_be_released(self, yard: Path) -> None:
        book_in(yard)
        run("material", "quarantine", "L-1", "--why", "no paperwork", book=yard)
        result = run("material", "release", "L-1", "--by", "j.mercer", book=yard)
        assert result.exit_code == EXIT_RULE
        assert "has not been tested" in result.output


class TestTheGateCannotBeWalkedRound:
    def test_release_before_test_is_refused(self, yard: Path) -> None:
        book_in(yard)
        result = run("material", "release", "L-1", "--by", "j.mercer", book=yard)
        assert result.exit_code == EXIT_RULE
        assert "has not been tested" in result.output

    def test_a_release_without_a_name_is_refused(self, yard: Path) -> None:
        book_in(yard)
        run("material", "test", "L-1", book=yard)
        assert run("material", "release", "L-1", book=yard).exit_code != 0

    def test_a_released_lot_cannot_be_held_afterwards(self, yard: Path) -> None:
        book_in(yard)
        run("material", "test", "L-1", book=yard)
        run("material", "release", "L-1", "--by", "j.mercer", book=yard)
        result = run("material", "quarantine", "L-1", "--why", "too late", book=yard)
        assert result.exit_code == EXIT_RULE
        assert "already in the system" in result.output

    def test_testing_twice_is_refused(self, yard: Path) -> None:
        book_in(yard)
        run("material", "test", "L-1", book=yard)
        result = run("material", "test", "L-1", book=yard)
        assert result.exit_code == EXIT_RULE
        assert "already been tested" in result.output


class TestABareCertificateIsNotAClearance:
    def test_verifying_nothing_says_so(self, yard: Path) -> None:
        book_in(yard)
        result = run("material", "verify", "L-1", book=yard)
        assert result.exit_code == 0
        assert "not a clearance" in result.output

    def test_it_still_releases_because_that_is_a_person_s_call(self, yard: Path) -> None:
        book_in(yard)
        run("material", "verify", "L-1", book=yard)
        run("material", "test", "L-1", book=yard)
        assert run("material", "release", "L-1", "--by", "j.mercer", book=yard).exit_code == 0

    def test_unchecked_claims_are_named_rather_than_ignored(self, yard: Path) -> None:
        book_in(yard, gfn="58.0", clay="0.30", moisture="0.20")
        result = run("material", "verify", "L-1", "--gfn", "58.2", book=yard)
        assert "did not check" in result.output
        assert "clay" in result.output
        assert "moisture" in result.output


class TestSeveralLots:
    def test_each_moves_independently(self, yard: Path) -> None:
        book_in(yard, "L-1")
        book_in(yard, "L-2")
        run("material", "test", "L-1", book=yard)
        run("material", "release", "L-1", "--by", "j.mercer", book=yard)
        listing = run("material", "held", book=yard)
        assert "L-2" in listing.output
        assert "L-1" not in listing.output

    def test_the_held_list_is_oldest_first(self, yard: Path) -> None:
        book_in(yard, "L-2")
        book_in(yard, "L-1")
        listing = run("material", "held", book=yard)
        assert listing.output.index("L-1") < listing.output.index("L-2")

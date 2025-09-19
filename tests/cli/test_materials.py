from __future__ import annotations

from pathlib import Path

import pytest

from mullerbox.cli.context import EXIT_RULE
from tests.cli.helpers import initialised, run


@pytest.fixture
def book(tmp_path: Path) -> Path:
    target = initialised(tmp_path)
    run(
        "material",
        "book-in",
        "L-1",
        "new sand",
        "48000",
        "--on",
        "2025-09-22",
        "--certificate",
        "COA-1",
        "--gfn",
        "58.0",
        "--clay",
        "0.30",
        book=target,
    )
    return target


class TestBookingIn:
    def test_a_lot_goes_on_the_book(self, tmp_path: Path) -> None:
        target = initialised(tmp_path)
        result = run(
            "material",
            "book-in",
            "L-1",
            "new sand",
            "48000",
            "--on",
            "2025-09-22",
            "--certificate",
            "COA-1",
            book=target,
        )
        assert result.exit_code == 0
        assert "booked in lot L-1" in result.output
        assert "claims 0 properties" in result.output

    def test_the_claims_are_counted(self, book: Path) -> None:
        result = run(
            "material",
            "book-in",
            "L-2",
            "bentonite",
            "4000",
            "--on",
            "2025-09-22",
            "--certificate",
            "COA-2",
            "--moisture",
            "0.2",
            book=book,
        )
        assert "claims 1 properties" in result.output

    def test_the_same_lot_twice_is_refused(self, book: Path) -> None:
        result = run(
            "material",
            "book-in",
            "L-1",
            "new sand",
            "48000",
            "--on",
            "2025-09-22",
            "--certificate",
            "COA-9",
            book=book,
        )
        assert result.exit_code == EXIT_RULE

    def test_an_unknown_material_lists_the_real_ones(self, tmp_path: Path) -> None:
        target = initialised(tmp_path)
        result = run(
            "material",
            "book-in",
            "L-1",
            "gravel",
            "48000",
            "--on",
            "2025-09-22",
            "--certificate",
            "COA-1",
            book=target,
        )
        assert result.exit_code == EXIT_RULE
        assert "is not a material" in result.output
        assert "bentonite" in result.output

    def test_a_bad_claim_is_refused(self, tmp_path: Path) -> None:
        target = initialised(tmp_path)
        result = run(
            "material",
            "book-in",
            "L-1",
            "new sand",
            "48000",
            "--on",
            "2025-09-22",
            "--certificate",
            "COA-1",
            "--gfn",
            "fine",
            book=target,
        )
        assert result.exit_code == EXIT_RULE
        assert "is not a grain fineness" in result.output


class TestVerifyChangesNothing:
    def test_agreement_is_reported(self, book: Path) -> None:
        result = run("material", "verify", "L-1", "--gfn", "58.5", "--clay", "0.32", book=book)
        assert result.exit_code == 0
        assert "fit to release" in result.output

    def test_a_discrepancy_is_reported_in_full(self, book: Path) -> None:
        result = run("material", "verify", "L-1", "--gfn", "70.0", book=book)
        assert "quarantine" in result.output
        assert "certificate says 58.0" in result.output

    def test_the_lot_is_not_released_by_verifying(self, book: Path) -> None:
        run("material", "verify", "L-1", "--gfn", "58.5", "--clay", "0.32", book=book)
        assert "L-1" in run("material", "held", book=book).output

    def test_unchecked_claims_are_named(self, book: Path) -> None:
        result = run("material", "verify", "L-1", "--gfn", "58.0", book=book)
        assert "did not check" in result.output
        assert "clay" in result.output

    def test_a_bare_certificate_is_not_a_clearance(self, tmp_path: Path) -> None:
        target = initialised(tmp_path)
        run(
            "material",
            "book-in",
            "L-9",
            "bentonite",
            "4000",
            "--on",
            "2025-09-22",
            "--certificate",
            "COA-9",
            book=target,
        )
        result = run("material", "verify", "L-9", book=target)
        assert "not a clearance" in result.output


class TestTheReleasePath:
    def test_test_then_release(self, book: Path) -> None:
        assert run("material", "test", "L-1", book=book).exit_code == 0
        result = run("material", "release", "L-1", "--by", "j.mercer", book=book)
        assert result.exit_code == 0
        assert "released by j.mercer" in result.output

    def test_releasing_something_untested_is_refused(self, book: Path) -> None:
        result = run("material", "release", "L-1", "--by", "j.mercer", book=book)
        assert result.exit_code == EXIT_RULE
        assert "has not been tested" in result.output

    def test_a_release_needs_a_name(self, book: Path) -> None:
        run("material", "test", "L-1", book=book)
        result = run("material", "release", "L-1", book=book)
        assert result.exit_code != 0

    def test_a_released_lot_leaves_the_held_list(self, book: Path) -> None:
        run("material", "test", "L-1", book=book)
        run("material", "release", "L-1", "--by", "j.mercer", book=book)
        assert "nothing held" in run("material", "held", book=book).output


class TestQuarantine:
    def test_it_holds_the_lot_with_a_reason(self, book: Path) -> None:
        result = run("material", "quarantine", "L-1", "--why", "too fine", book=book)
        assert result.exit_code == 0
        held = run("material", "held", book=book)
        assert "quarantined" in held.output
        assert "too fine" in held.output

    def test_a_released_lot_cannot_be_quarantined(self, book: Path) -> None:
        run("material", "test", "L-1", book=book)
        run("material", "release", "L-1", "--by", "j.mercer", book=book)
        result = run("material", "quarantine", "L-1", "--why", "too fine", book=book)
        assert result.exit_code == EXIT_RULE
        assert "already in the system" in result.output


class TestHeld:
    def test_an_empty_book_says_nothing_held(self, tmp_path: Path) -> None:
        target = initialised(tmp_path)
        assert "nothing held" in run("material", "held", book=target).output

    def test_a_delivered_lot_is_held(self, book: Path) -> None:
        result = run("material", "held", book=book)
        assert "L-1" in result.output
        assert "delivered" in result.output

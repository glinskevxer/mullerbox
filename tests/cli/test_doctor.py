from __future__ import annotations

from pathlib import Path

import pytest

from tests.cli.helpers import initialised, run

WHEN = "2025-12-22"


def healthy(tmp_path: Path) -> Path:
    """A book with nothing wrong with it."""
    book = initialised(tmp_path)
    run("catalogue", "load-afs", book=book)
    run("catalogue", "instrument-add", "RAM-1", "compactability", book=book)
    run("catalogue", "calibrate", "RAM-1", "C-1", "--on", "2025-01-06", "--days", "700", book=book)
    run("spec", "load-default", "--on", "2025-01-06", book=book)
    for material, rate in (
        ("bentonite", "142.00"),
        ("seacoal", "196.50"),
        ("new sand", "38.25"),
        ("water", "0"),
    ):
        run("cost", "set-price", material, rate, "--from", "2025-01-06", book=book)
    run(
        "programme",
        "set",
        "comp",
        "every_shift",
        "--on",
        "2025-01-06",
        "--because",
        "line critical",
        book=book,
    )
    run("lab", "sample-add", "S-1", "--on", WHEN, "--point", "muller", "--system", "two", book=book)
    run("lab", "result-add", "S-1", "comp", "42", "--instrument", "RAM-1", "--on", WHEN, book=book)
    run(
        "system",
        "inventory",
        "--name",
        "two",
        "--on",
        "2025-12-01",
        "--vessel",
        "silo:1000:0.80:95",
        book=book,
    )
    return book


class TestAHealthyBook:
    def test_it_says_so_in_one_line(self, tmp_path: Path) -> None:
        book = healthy(tmp_path)
        result = run("doctor", "--on", WHEN, book=book)
        assert result.exit_code == 0
        assert "the book is sound" in result.output

    def test_it_changes_nothing(self, tmp_path: Path) -> None:
        book = healthy(tmp_path)
        before = book.read_bytes()
        run("doctor", "--on", WHEN, book=book)
        assert book.read_bytes() == before


class TestFindings:
    def test_a_book_behind_the_code_reports_only_the_schema(self, tmp_path: Path) -> None:
        """Every other check would raise on tables that are not there yet."""
        book = tmp_path / "shop.sqlite3"
        result = run("doctor", "--on", WHEN, book=book)
        assert result.exit_code == 0
        assert "the book is at migration 0" in result.output
        assert "1 findings" in result.output
        assert "calibration" not in result.output

    def test_a_lapse_only_costs_when_a_reading_fell_inside_it(self, tmp_path: Path) -> None:
        """A certificate expiring does not reach back over readings it covered."""
        book = healthy(tmp_path)
        clean = run("doctor", "--on", "2027-01-01", book=book)
        assert "invalidating" not in clean.output

        # A reading taken after the certificate ran out is a different matter.
        run(
            "lab",
            "sample-add",
            "S-2",
            "--on",
            "2027-01-05",
            "--point",
            "muller",
            "--system",
            "two",
            book=book,
        )
        run(
            "lab",
            "result-add",
            "S-2",
            "comp",
            "42",
            "--instrument",
            "RAM-1",
            "--on",
            "2027-01-05",
            book=book,
        )
        result = run("doctor", "--on", "2027-02-01", book=book)
        assert "costing now" in result.output
        assert "invalidating 1 readings" in result.output

    def test_a_lapse_with_no_readings_behind_it_only_will_bite(self, tmp_path: Path) -> None:
        book = initialised(tmp_path)
        run("catalogue", "instrument-add", "RAM-1", "compactability", book=book)
        result = run("doctor", "--on", WHEN, book=book)
        assert "has no calibration covering" in result.output
        assert "invalidating" not in result.output

    def test_a_missing_spec_sheet_is_costing_now(self, tmp_path: Path) -> None:
        book = initialised(tmp_path)
        result = run("doctor", "--on", WHEN, book=book)
        assert "no spec sheet was published" in result.output

    def test_missing_prices_are_only_worth_knowing(self, tmp_path: Path) -> None:
        book = healthy(tmp_path)
        result = run("doctor", "--on", WHEN, book=book)
        assert "no price for" not in result.output

    def test_an_unpriced_book_says_which_materials(self, tmp_path: Path) -> None:
        book = initialised(tmp_path)
        result = run("doctor", "--on", WHEN, book=book)
        assert "no price for" in result.output
        assert "bentonite" in result.output

    def test_an_empty_programme_is_reported(self, tmp_path: Path) -> None:
        book = initialised(tmp_path)
        result = run("doctor", "--on", WHEN, book=book)
        assert "no property is on the testing programme" in result.output

    def test_overdue_tests_are_reported_with_the_worst(self, tmp_path: Path) -> None:
        book = healthy(tmp_path)
        result = run("doctor", "--on", "2026-06-01", book=book)
        assert "tests are due" in result.output

    def test_no_screen_series_is_reported(self, tmp_path: Path) -> None:
        book = initialised(tmp_path)
        result = run("doctor", "--on", WHEN, book=book)
        assert "no screen series" in result.output


class TestRanking:
    def test_the_worst_comes_first(self, tmp_path: Path) -> None:
        book = healthy(tmp_path)
        run(
            "lab",
            "sample-add",
            "S-2",
            "--on",
            "2027-01-05",
            "--point",
            "muller",
            "--system",
            "two",
            book=book,
        )
        run(
            "lab",
            "result-add",
            "S-2",
            "comp",
            "42",
            "--instrument",
            "RAM-1",
            "--on",
            "2027-01-05",
            book=book,
        )
        result = run("doctor", "--on", "2027-02-01", book=book)
        lines = [x for x in result.output.split("\n") if x.strip()]
        body = [x for x in lines if "costing now" in x or "will bite" in x]
        assert body
        assert "costing now" in body[0]

    def test_the_summary_names_the_worst_severity(self, tmp_path: Path) -> None:
        book = healthy(tmp_path)
        run(
            "lab",
            "sample-add",
            "S-2",
            "--on",
            "2027-01-05",
            "--point",
            "muller",
            "--system",
            "two",
            book=book,
        )
        run(
            "lab",
            "result-add",
            "S-2",
            "comp",
            "42",
            "--instrument",
            "RAM-1",
            "--on",
            "2027-01-05",
            book=book,
        )
        result = run("doctor", "--on", "2027-02-01", book=book)
        assert "worst is costing now" in result.output

    def test_a_bad_date_names_the_format(self, tmp_path: Path) -> None:
        book = healthy(tmp_path)
        result = run("doctor", "--on", "22/12/2025", book=book)
        assert result.exit_code != 0
        assert "yyyy-mm-dd" in result.output


@pytest.fixture
def counted(tmp_path: Path) -> Path:
    """A healthy book with its inventory removed, to exercise the new finding."""
    book = healthy(tmp_path)
    run("system", "count-delete", "--name", "two", "--on", "2025-12-01", book=book)
    return book


class TestTheInventoryFinding:
    def take(self, counted: Path, when: str, name: str = "two", complete: bool = True) -> None:
        args = [
            "system",
            "inventory",
            "--name",
            name,
            "--on",
            when,
            "--vessel",
            "silo:1000:0.80:95",
        ]
        if not complete:
            args += ["--vessel", "hopper:400:0.50"]
        assert run(*args, book=counted).exit_code == 0

    def test_a_book_with_no_count_says_so(self, counted: Path) -> None:
        shown = run("doctor", "--on", "2026-01-05", book=counted)
        assert "no sand system has ever been inventoried" in shown.output

    def test_a_fresh_count_raises_nothing(self, counted: Path) -> None:
        self.take(counted, "2026-01-02")
        shown = run("doctor", "--on", "2026-01-05", book=counted)
        assert "inventoried" not in shown.output
        assert "last counted" not in shown.output

    def test_a_stale_count_is_costing_now(self, counted: Path) -> None:
        self.take(counted, "2025-01-06")
        shown = run("doctor", "--on", "2026-01-05", book=counted)
        assert "last counted 364 days ago" in shown.output
        assert "costing now" in shown.output

    def test_a_partial_latest_count_is_named(self, counted: Path) -> None:
        self.take(counted, "2026-01-02", complete=False)
        shown = run("doctor", "--on", "2026-01-05", book=counted)
        assert "did not reach hopper" in shown.output

    def test_a_count_only_in_the_future_is_worth_knowing(self, counted: Path) -> None:
        self.take(counted, "2026-06-01")
        shown = run("doctor", "--on", "2026-01-05", book=counted)
        assert "no count on or before 2026-01-05" in shown.output

    def test_each_system_is_read_on_its_own(self, counted: Path) -> None:
        self.take(counted, "2025-01-06", name="one")
        self.take(counted, "2026-01-02", name="two")
        shown = run("doctor", "--on", "2026-01-05", book=counted)
        assert "one was last counted" in shown.output
        assert "two was last counted" not in shown.output

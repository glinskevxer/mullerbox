from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from typing import Any

import pytest

from mullerbox.errors import BadInputError, DuplicateError, NotFoundError, RuleError
from mullerbox.gfn.fineness import fineness_of
from mullerbox.screens.analysis import SieveAnalysis
from mullerbox.screens.series import AFS_US_SERIES, ScreenSeries, Step
from mullerbox.store.connection import Book
from mullerbox.store.result_repo import Sample, save_sample
from mullerbox.store.series_repo import save_series
from mullerbox.store.sieve_repo import (
    analysis_exists,
    delete_analysis,
    load_analysis,
    samples_with_analyses,
    save_analysis,
)
from mullerbox.units.mass import Grams
from mullerbox.units.mesh import Mesh
from tests.gfn.helpers import analysis_of, sheet
from tests.store.helpers import migrated_book

SAND = {"50": "8.00", "70": "22.00", "100": "16.00", "140": "4.00"}

SMALL = ScreenSeries(
    name="three screen rig",
    steps=(
        Step(Mesh(30, 600), 20),
        Step(Mesh(70, 212), 50),
        Step(Mesh.pan(), 300),
    ),
)


@pytest.fixture
def book() -> Iterator[Book]:
    with migrated_book() as opened:
        save_series(opened, AFS_US_SERIES)
        save_sample(
            opened,
            Sample(
                sample_id="S-100",
                taken_on=date(2025, 5, 12),
                point="muller discharge",
                system_name="number two system",
            ),
        )
        yield opened


def analysis() -> SieveAnalysis:
    return analysis_of(sheet(**SAND), "50.00")


class TestRoundTrip:
    def test_an_analysis_comes_back_identical(self, book: Book) -> None:
        original = analysis()
        save_analysis(book, "S-100", original)
        loaded = load_analysis(book, "S-100")
        assert loaded.charged == original.charged
        assert loaded.recovered == original.recovered
        assert loaded.distribution == original.distribution

    def test_the_fineness_survives_the_round_trip(self, book: Book) -> None:
        save_analysis(book, "S-100", analysis())
        assert fineness_of(load_analysis(book, "S-100")).value == (fineness_of(analysis()).value)

    def test_the_masses_survive_to_the_centigram(self, book: Book) -> None:
        save_analysis(book, "S-100", analysis())
        loaded = load_analysis(book, "S-100")
        on_seventy = next(r for r in loaded.readings if r.mesh.number == 70)
        assert on_seventy.mass == Grams("22.00")

    def test_every_screen_including_the_empty_ones_is_kept(self, book: Book) -> None:
        save_analysis(book, "S-100", analysis())
        assert len(load_analysis(book, "S-100").readings) == len(AFS_US_SERIES)


class TestBookkeeping:
    def test_saving_twice_is_refused(self, book: Book) -> None:
        save_analysis(book, "S-100", analysis())
        with pytest.raises(DuplicateError, match="sieve analysis on sample"):
            save_analysis(book, "S-100", analysis())

    def test_an_analysis_against_a_missing_sample_is_refused(self, book: Book) -> None:
        with pytest.raises(NotFoundError, match="sample"):
            save_analysis(book, "S-999", analysis())

    def test_an_analysis_on_an_unknown_series_is_refused(self, book: Book) -> None:
        book.execute("DELETE FROM screen_step")
        book.execute("DELETE FROM screen_series")
        with pytest.raises(RuleError, match="which is not on the book"):
            save_analysis(book, "S-100", analysis())

    def test_loading_something_absent_is_refused(self, book: Book) -> None:
        with pytest.raises(NotFoundError, match="sieve analysis on sample"):
            load_analysis(book, "S-100")

    def test_exists_and_listing(self, book: Book) -> None:
        assert not analysis_exists(book, "S-100")
        assert samples_with_analyses(book) == []
        save_analysis(book, "S-100", analysis())
        assert analysis_exists(book, "S-100")
        assert samples_with_analyses(book) == ["S-100"]

    def test_deleting(self, book: Book) -> None:
        save_analysis(book, "S-100", analysis())
        delete_analysis(book, "S-100")
        assert not analysis_exists(book, "S-100")

    def test_deleting_something_absent_is_refused(self, book: Book) -> None:
        with pytest.raises(NotFoundError, match="sieve analysis on sample"):
            delete_analysis(book, "S-100")

    def test_it_wants_an_analysis(self, book: Book) -> None:
        bad: Any = "50 g"
        with pytest.raises(BadInputError, match="sieve analysis is expected"):
            save_analysis(book, "S-100", bad)


class TestTamperedRows:
    def test_two_series_on_one_sample_is_refused(self, book: Book) -> None:
        save_analysis(book, "S-100", analysis())
        # The foreign key stops a rename to nothing, so a second real series
        # has to exist before the rows can be split across two.
        save_series(book, SMALL)
        book.execute(
            "UPDATE sieve_reading SET series_name = ? WHERE mesh_number = 70",
            (SMALL.name,),
        )
        with pytest.raises(RuleError, match="different series"):
            load_analysis(book, "S-100")

    def test_two_charged_masses_on_one_sample_is_refused(self, book: Book) -> None:
        save_analysis(book, "S-100", analysis())
        book.execute("UPDATE sieve_reading SET charged_cg = 9999 WHERE mesh_number = 70")
        with pytest.raises(RuleError, match="2 charged masses"):
            load_analysis(book, "S-100")

    def test_a_screen_off_the_series_is_refused(self, book: Book) -> None:
        save_analysis(book, "S-100", analysis())
        book.execute("UPDATE sieve_reading SET mesh_number = 325 WHERE mesh_number = 70")
        with pytest.raises(RuleError, match="which is not on series"):
            load_analysis(book, "S-100")

    def test_a_missing_screen_is_caught_by_the_type(self, book: Book) -> None:
        save_analysis(book, "S-100", analysis())
        book.execute("DELETE FROM sieve_reading WHERE mesh_number = 70")
        with pytest.raises(RuleError, match="no reading for screen 70"):
            load_analysis(book, "S-100")

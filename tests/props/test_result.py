from __future__ import annotations

from datetime import date

import pytest

from mullerbox.cal.instrument import Instrument, InstrumentKind
from mullerbox.errors import BadInputError, RuleError
from mullerbox.props.kind import PropertyKind
from mullerbox.props.result import Result, countable, latest_countable
from mullerbox.units.percent import Percent
from mullerbox.units.pressure import Psi
from tests.props.helpers import Q1, Q2, rammer, result, usm

IN_WINDOW = date(2025, 2, 3)
IN_LAPSE = date(2025, 4, 10)


class TestConstruction:
    def test_a_result_wants_a_property(self) -> None:
        with pytest.raises(BadInputError, match="result for a property"):
            Result(
                kind="compactability",  # type: ignore[arg-type]
                reading=Percent(42),
                instrument_tag="RAM-1",
                tested_on=IN_WINDOW,
                sample_id="S-100",
            )

    def test_the_reading_has_to_be_on_the_right_scale(self) -> None:
        with pytest.raises(BadInputError, match="measured in Percent, not Psi"):
            result(Psi(22))

    def test_a_result_names_its_instrument_sample_and_date(self) -> None:
        with pytest.raises(BadInputError, match="names the instrument"):
            result(Percent(42), tag="  ")
        with pytest.raises(BadInputError, match="names the sample"):
            result(Percent(42), sample="  ")
        with pytest.raises(BadInputError, match="is dated"):
            result(Percent(42), when="2025-02-03")  # type: ignore[arg-type]


class TestValidityIsNotStoredOnTheResult:
    def test_a_result_inside_a_window_counts(self) -> None:
        assert result(Percent(42)).counts_for(rammer())

    def test_a_result_inside_a_lapse_does_not(self) -> None:
        assert not result(Percent(42), when=IN_LAPSE).counts_for(rammer(Q1, Q2))

    def test_the_same_result_changes_answer_when_the_record_changes(self) -> None:
        reading = result(Percent(42), when=IN_LAPSE)
        before = rammer(Q1, Q2)
        assert not reading.counts_for(before)

        from mullerbox.cal.window import CalibrationWindow

        filler = CalibrationWindow(date(2025, 4, 6), date(2025, 4, 20), "C-3")
        after = before.with_window(filler)
        assert reading.counts_for(after)

    def test_requiring_names_the_sample_the_date_and_the_instrument(self) -> None:
        with pytest.raises(
            RuleError,
            match="compactability on sample S-100 was run on 2025-04-10, "
            "when RAM-1 had no calibration",
        ):
            result(Percent(42), when=IN_LAPSE).require_counts(rammer(Q1, Q2))

    def test_requiring_passes_quietly_when_it_counts(self) -> None:
        result(Percent(42)).require_counts(rammer())

    def test_the_backing_certificate_comes_back(self) -> None:
        assert result(Percent(42)).certificate_for(rammer()) == "C-1"

    def test_there_is_no_certificate_in_a_lapse(self) -> None:
        assert result(Percent(42), when=IN_LAPSE).certificate_for(rammer(Q1, Q2)) is None


class TestTheInstrumentHasToBeTheRightOne:
    def test_another_instruments_history_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="came off RAM-1, not USM-1"):
            result(Percent(42)).counts_for(usm())

    def test_an_instrument_of_the_wrong_kind_is_refused(self) -> None:
        mislabelled = Instrument(tag="RAM-1", kind=InstrumentKind.PERMEABILITY, windows=(Q1,))
        with pytest.raises(BadInputError, match="measured on the compactability rammer"):
            result(Percent(42)).counts_for(mislabelled)

    def test_it_wants_an_instrument(self) -> None:
        with pytest.raises(BadInputError, match="checked against an instrument"):
            result(Percent(42)).counts_for("RAM-1")  # type: ignore[arg-type]


class TestFiltering:
    def test_it_keeps_only_what_counts(self) -> None:
        good = result(Percent(42))
        bad = result(Percent(44), when=IN_LAPSE)
        kept = countable([good, bad], {"RAM-1": rammer(Q1, Q2)})
        assert kept == [good]

    def test_an_unknown_tag_is_dropped_rather_than_raised_on(self) -> None:
        stray = result(Percent(42), tag="RAM-9")
        assert countable([stray], {"RAM-1": rammer()}) == []

    def test_an_instrument_of_the_wrong_kind_is_dropped(self) -> None:
        wrong = Instrument(tag="RAM-1", kind=InstrumentKind.MUFFLE, windows=(Q1,))
        assert countable([result(Percent(42))], {"RAM-1": wrong}) == []


class TestLatest:
    def test_it_takes_the_most_recent_usable_reading(self) -> None:
        old = result(Percent(40), when=date(2025, 2, 1))
        new = result(Percent(43), when=date(2025, 3, 1))
        found = latest_countable(
            [old, new], {"RAM-1": rammer()}, PropertyKind.COMPACTABILITY, date(2025, 4, 1)
        )
        assert found == new

    def test_it_ignores_readings_after_the_cutoff(self) -> None:
        old = result(Percent(40), when=date(2025, 2, 1))
        new = result(Percent(43), when=date(2025, 3, 1))
        found = latest_countable(
            [old, new], {"RAM-1": rammer()}, PropertyKind.COMPACTABILITY, date(2025, 2, 15)
        )
        assert found == old

    def test_a_lapse_makes_an_older_reading_the_current_one(self) -> None:
        good = result(Percent(40), when=date(2025, 2, 1))
        voided = result(Percent(43), when=IN_LAPSE)
        found = latest_countable(
            [good, voided],
            {"RAM-1": rammer(Q1, Q2)},
            PropertyKind.COMPACTABILITY,
            date(2025, 4, 15),
        )
        assert found == good

    def test_two_on_one_day_take_the_later_entry(self) -> None:
        first = result(Percent(40), sample="S-1")
        second = result(Percent(43), sample="S-2")
        found = latest_countable(
            [first, second],
            {"RAM-1": rammer()},
            PropertyKind.COMPACTABILITY,
            date(2025, 4, 1),
        )
        assert found == second

    def test_nothing_usable_gives_nothing(self) -> None:
        assert latest_countable([], {}, PropertyKind.COMPACTABILITY, date(2025, 4, 1)) is None

    def test_another_property_is_not_returned(self) -> None:
        gcs = result(Psi(22), kind=PropertyKind.GREEN_COMPRESSION, tag="USM-1")
        found = latest_countable(
            [gcs], {"USM-1": usm()}, PropertyKind.COMPACTABILITY, date(2025, 4, 1)
        )
        assert found is None

    def test_the_arguments_are_checked(self) -> None:
        with pytest.raises(BadInputError, match="property kind is expected"):
            latest_countable([], {}, "comp", date(2025, 4, 1))  # type: ignore[arg-type]
        with pytest.raises(BadInputError, match="cutoff date is expected"):
            latest_countable([], {}, PropertyKind.COMPACTABILITY, "2025-04-01")  # type: ignore[arg-type]


def test_str_reads_like_a_bench_line() -> None:
    assert str(result(Percent(42))) == "S-100 compactability 42.00% on 2025-02-03"

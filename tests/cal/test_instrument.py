from __future__ import annotations

from datetime import date

import pytest

from mullerbox.cal.instrument import Instrument, InstrumentKind
from mullerbox.cal.window import CalibrationWindow
from mullerbox.errors import BadInputError, RuleError

Q1 = CalibrationWindow(date(2025, 1, 6), date(2025, 4, 6), "C-1")
Q2 = CalibrationWindow(date(2025, 4, 6), date(2025, 7, 6), "C-2")
LATE = CalibrationWindow(date(2025, 4, 20), date(2025, 7, 20), "C-3")


def gcs(*windows: CalibrationWindow) -> Instrument:
    return Instrument(tag="USM-1", kind=InstrumentKind.STRENGTH, windows=windows)


class TestConstruction:
    def test_an_instrument_needs_a_tag_and_a_kind(self) -> None:
        with pytest.raises(BadInputError, match="needs a tag"):
            Instrument(tag="  ", kind=InstrumentKind.STRENGTH)
        with pytest.raises(BadInputError, match="needs a kind"):
            Instrument(tag="USM-1", kind="strength")  # type: ignore[arg-type]

    def test_windows_have_to_be_windows(self) -> None:
        with pytest.raises(BadInputError, match="carries calibration windows"):
            Instrument(tag="USM-1", kind=InstrumentKind.STRENGTH, windows=("C-1",))  # type: ignore[arg-type]

    def test_windows_are_kept_in_order(self) -> None:
        with pytest.raises(BadInputError, match="in calibration order"):
            gcs(Q2, Q1)

    def test_overlapping_certificates_are_refused(self) -> None:
        overlapping = CalibrationWindow(date(2025, 3, 1), date(2025, 6, 1), "C-9")
        with pytest.raises(RuleError, match="both cover"):
            gcs(Q1, overlapping)

    def test_a_repeated_certificate_number_is_refused(self) -> None:
        again = CalibrationWindow(date(2025, 4, 6), date(2025, 7, 6), "C-1")
        with pytest.raises(RuleError, match="recorded twice"):
            gcs(Q1, again)

    def test_an_instrument_may_have_no_calibration_at_all(self) -> None:
        assert gcs().windows == ()
        assert gcs().latest is None


class TestCoverage:
    def test_the_covering_certificate_comes_back(self) -> None:
        found = gcs(Q1, Q2).window_covering(date(2025, 2, 1))
        assert found is not None
        assert found.certificate == "C-1"

    def test_back_to_back_windows_have_no_gap(self) -> None:
        instrument = gcs(Q1, Q2)
        assert instrument.was_calibrated_on(date(2025, 4, 6))
        assert instrument.lapses() == ()

    def test_a_lapse_leaves_a_hole(self) -> None:
        instrument = gcs(Q1, LATE)
        assert not instrument.was_calibrated_on(date(2025, 4, 10))
        assert instrument.lapses() == ((date(2025, 4, 6), date(2025, 4, 20)),)

    def test_the_hole_is_half_open_at_both_ends(self) -> None:
        instrument = gcs(Q1, LATE)
        assert not instrument.was_calibrated_on(date(2025, 4, 6))
        assert instrument.was_calibrated_on(date(2025, 4, 5))
        assert instrument.was_calibrated_on(date(2025, 4, 20))

    def test_nothing_covers_a_date_before_the_first_certificate(self) -> None:
        assert gcs(Q1).window_covering(date(2024, 12, 1)) is None

    def test_coverage_wants_a_date(self) -> None:
        with pytest.raises(BadInputError, match="checked against a date"):
            gcs(Q1).window_covering("2025-02-01")  # type: ignore[arg-type]


class TestRequire:
    def test_it_hands_back_the_certificate(self) -> None:
        assert gcs(Q1).require_calibrated(date(2025, 2, 1)).certificate == "C-1"

    def test_it_names_the_instrument_and_the_date_on_a_lapse(self) -> None:
        with pytest.raises(RuleError, match="USM-1 had no calibration covering 2025-04-10"):
            gcs(Q1, LATE).require_calibrated(date(2025, 4, 10))


class TestAddingACalibration:
    def test_a_late_entry_sorts_into_place(self) -> None:
        built = gcs(Q2).with_window(Q1)
        assert [w.certificate for w in built.windows] == ["C-1", "C-2"]

    def test_a_late_entry_closes_a_lapse_that_was_open(self) -> None:
        before = gcs(Q1, LATE)
        assert not before.was_calibrated_on(date(2025, 4, 10))
        filler = CalibrationWindow(date(2025, 4, 6), date(2025, 4, 20), "C-4")
        after = before.with_window(filler)
        assert after.was_calibrated_on(date(2025, 4, 10))
        assert after.lapses() == ()

    def test_adding_an_overlapping_certificate_is_refused(self) -> None:
        clash = CalibrationWindow(date(2025, 3, 1), date(2025, 6, 1), "C-9")
        with pytest.raises(RuleError, match="both cover"):
            gcs(Q1).with_window(clash)

    def test_adding_wants_a_window(self) -> None:
        with pytest.raises(BadInputError, match="carries calibration windows"):
            gcs().with_window("C-1")  # type: ignore[arg-type]

    def test_the_original_is_untouched(self) -> None:
        original = gcs(Q1)
        original.with_window(Q2)
        assert len(original.windows) == 1


class TestPresentation:
    def test_latest_is_the_last_calibration(self) -> None:
        assert gcs(Q1, Q2).latest == Q2

    def test_str_names_the_tag_and_the_kind(self) -> None:
        assert str(gcs()) == "USM-1 (universal strength machine)"

    def test_every_kind_has_a_label(self) -> None:
        assert all(k.label for k in InstrumentKind)

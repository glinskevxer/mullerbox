from __future__ import annotations

from decimal import Decimal

import pytest

from mullerbox.errors import BadInputError, RuleError
from mullerbox.screens.analysis import Retained, SieveAnalysis
from mullerbox.screens.series import ScreenSeries
from mullerbox.units.mass import Grams
from mullerbox.units.mesh import Mesh
from mullerbox.units.percent import Percent


class TestConstruction:
    def test_every_screen_has_to_have_a_reading(
        self, sheet: dict[str, object], series: ScreenSeries
    ) -> None:
        short = dict(sheet)
        del short["140"]
        with pytest.raises(RuleError, match="no reading for screen 140"):
            SieveAnalysis.of(series, "43.70", short)

    def test_a_screen_off_the_series_is_refused(
        self, sheet: dict[str, object], series: ScreenSeries
    ) -> None:
        with pytest.raises(RuleError, match="is not on series"):
            SieveAnalysis.of(series, "50.00", {**sheet, "325": "0.10"})

    def test_a_screen_weighed_twice_is_refused(self, series: ScreenSeries) -> None:
        doubled = (
            Retained(Mesh(50, 300), Grams("8.40")),
            Retained(Mesh(50, 300), Grams("8.40")),
        )
        with pytest.raises(RuleError, match="weighed twice"):
            SieveAnalysis(series=series, charged=Grams("50.00"), readings=doubled)

    def test_nothing_charged_is_refused(
        self, sheet: dict[str, object], series: ScreenSeries
    ) -> None:
        with pytest.raises(BadInputError, match="nothing was charged"):
            SieveAnalysis.of(series, "0", sheet)

    def test_the_pieces_have_to_be_the_right_types(self, series: ScreenSeries) -> None:
        with pytest.raises(BadInputError, match="run against a series"):
            SieveAnalysis(series="afs", charged=Grams(50), readings=())  # type: ignore[arg-type]
        with pytest.raises(BadInputError, match="charged mass is a mass"):
            SieveAnalysis(series=series, charged="50", readings=())  # type: ignore[arg-type]
        with pytest.raises(BadInputError, match="from retained readings"):
            SieveAnalysis(series=series, charged=Grams(50), readings=("50",))  # type: ignore[arg-type]

    def test_a_retained_reading_checks_its_own_types(self) -> None:
        with pytest.raises(BadInputError, match="against a screen"):
            Retained("50", Grams(1))  # type: ignore[arg-type]
        with pytest.raises(BadInputError, match="is a mass"):
            Retained(Mesh(50, 300), "1")  # type: ignore[arg-type]


class TestClosure:
    def test_a_stack_that_closes_exactly(self, analysis: SieveAnalysis) -> None:
        assert analysis.recovered == Grams("50.00")
        assert analysis.loss == Grams.zero()
        assert analysis.closure_error == Percent.zero()
        assert analysis.closes

    def test_a_small_loss_still_closes(
        self, sheet: dict[str, object], series: ScreenSeries
    ) -> None:
        light = SieveAnalysis.of(series, "50.20", sheet)
        assert light.loss == Grams("0.20")
        assert light.closure_error.value == Decimal("0.40")
        assert light.closes
        light.require_closure()

    def test_a_big_loss_voids_the_analysis(
        self, sheet: dict[str, object], series: ScreenSeries
    ) -> None:
        heavy = SieveAnalysis.of(series, "52.00", sheet)
        assert not heavy.closes
        with pytest.raises(RuleError, match="past the 0.5% closure tolerance"):
            heavy.require_closure()

    def test_closure_is_measured_against_the_charge_not_the_recovery(
        self, series: ScreenSeries, sheet: dict[str, object]
    ) -> None:
        out = SieveAnalysis.of(series, "51.00", sheet)
        assert out.closure_error == Percent.of(Decimal("1.00"), Decimal("51.00"))

    def test_gaining_mass_is_a_closure_failure_too(
        self, sheet: dict[str, object], series: ScreenSeries
    ) -> None:
        gained = SieveAnalysis.of(series, "48.00", sheet)
        assert gained.loss == Grams("2.00")
        assert not gained.closes

    def test_an_empty_stack_is_refused(
        self, sheet: dict[str, object], series: ScreenSeries
    ) -> None:
        nothing = SieveAnalysis.of(series, "50.00", dict.fromkeys(sheet, "0"))
        with pytest.raises(RuleError, match="nothing came back"):
            nothing.require_closure()


class TestDistribution:
    def test_the_fractions_are_taken_against_the_recovery(
        self, sheet: dict[str, object], series: ScreenSeries
    ) -> None:
        light = SieveAnalysis.of(series, "50.20", sheet)
        assert light.fraction_on(Mesh(70, 212)) == Percent.of(Decimal("15.60"), Decimal("50.00"))

    def test_the_fractions_sum_to_a_hundred(self, analysis: SieveAnalysis) -> None:
        assert sum((pct.value for _, pct in analysis.distribution), Decimal(0)) == Decimal(100)

    def test_the_distribution_reads_coarse_first(self, analysis: SieveAnalysis) -> None:
        labels = [mesh.label for mesh, _ in analysis.distribution]
        assert labels[0] == "6"
        assert labels[-1] == "PAN"

    def test_readings_out_of_order_still_report_in_stack_order(
        self, sheet: dict[str, object], series: ScreenSeries
    ) -> None:
        reversed_sheet = dict(reversed(list(sheet.items())))
        built = SieveAnalysis.of(series, "50.00", reversed_sheet)
        assert [m.label for m, _ in built.distribution][:3] == ["6", "12", "20"]

    def test_the_pan_fraction_is_the_fines(self, analysis: SieveAnalysis) -> None:
        assert analysis.pan_fraction == Percent("0.80")

    def test_a_screen_not_on_the_analysis_is_refused(self, analysis: SieveAnalysis) -> None:
        with pytest.raises(BadInputError, match="was not weighed"):
            analysis.fraction_on(Mesh(50, 297))

    def test_a_void_analysis_will_not_hand_out_fractions(
        self, sheet: dict[str, object], series: ScreenSeries
    ) -> None:
        heavy = SieveAnalysis.of(series, "52.00", sheet)
        with pytest.raises(RuleError, match="closure tolerance"):
            assert heavy.distribution
        with pytest.raises(RuleError, match="closure tolerance"):
            heavy.fraction_on(Mesh(70, 212))

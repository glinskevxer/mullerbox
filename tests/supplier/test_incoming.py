from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from mullerbox.addition.material import Material
from mullerbox.errors import BadInputError
from mullerbox.supplier.incoming import FINENESS_TOLERANCE, verify
from mullerbox.supplier.lot import Certificate, Lot
from mullerbox.units.bulk import Pounds
from mullerbox.units.percent import Percent


def lot_with(**claims: Any) -> Lot:
    return Lot(
        lot_id="L-1",
        material=Material.NEW_SAND,
        mass=Pounds.of_tons(24),
        delivered_on=date(2025, 9, 1),
        certificate=Certificate(number="COA-1", **claims),
    )


class TestAgreement:
    def test_a_lot_inside_tolerance_agrees(self) -> None:
        got = verify(
            lot_with(grain_fineness=Decimal("58.0")),
            grain_fineness=Decimal("59.5"),
        )
        assert got.agrees
        assert got.checked == ("grain_fineness",)
        assert "fit to release" in got.recommendation()

    def test_exactly_on_the_tolerance_agrees(self) -> None:
        got = verify(
            lot_with(grain_fineness=Decimal("58.0")),
            grain_fineness=Decimal("58.0") + FINENESS_TOLERANCE,
        )
        assert got.agrees

    def test_just_past_it_does_not(self) -> None:
        got = verify(
            lot_with(grain_fineness=Decimal("58.0")),
            grain_fineness=Decimal("61.5"),
        )
        assert not got.agrees
        assert "quarantine" in got.recommendation()

    def test_the_gap_carries_its_sign(self) -> None:
        got = verify(
            lot_with(grain_fineness=Decimal("58.0")),
            grain_fineness=Decimal("50.0"),
        )
        assert got.discrepancies[0].gap == Decimal("-8.0")
        assert "-8.0" in str(got.discrepancies[0])

    def test_several_claims_at_once(self) -> None:
        got = verify(
            lot_with(grain_fineness=Decimal("58.0"), clay=Percent("0.30")),
            grain_fineness=Decimal("58.5"),
            clay=Percent("0.35"),
        )
        assert set(got.checked) == {"grain_fineness", "clay"}
        assert got.agrees

    def test_percentages_and_decimals_both_read(self) -> None:
        got = verify(lot_with(clay=Percent("0.30")), clay=Decimal("0.35"))
        assert got.agrees


class TestAnEmptyCertificateIsNotAPass:
    def test_a_bare_certificate_checks_nothing(self) -> None:
        got = verify(lot_with(), grain_fineness=Decimal("58.0"))
        assert got.checked_nothing
        assert got.checked == ()

    def test_it_says_so_rather_than_passing(self) -> None:
        got = verify(lot_with())
        assert got.agrees
        assert "not a clearance" in got.recommendation()

    def test_a_real_check_does_not_say_that(self) -> None:
        got = verify(lot_with(grain_fineness=Decimal("58.0")), grain_fineness=Decimal("58.0"))
        assert "not a clearance" not in got.recommendation()


class TestUncheckedClaims:
    def test_a_claim_the_lab_did_not_measure_is_reported(self) -> None:
        got = verify(
            lot_with(grain_fineness=Decimal("58.0"), clay=Percent("0.30")),
            grain_fineness=Decimal("58.0"),
        )
        assert got.unchecked == ("clay",)
        assert got.checked == ("grain_fineness",)

    def test_an_unchecked_claim_does_not_count_as_agreement(self) -> None:
        got = verify(
            lot_with(clay=Percent("0.30")),
        )
        assert got.checked_nothing
        assert got.unchecked == ("clay",)

    def test_a_measurement_with_no_claim_behind_it_is_ignored(self) -> None:
        # The lab measured clay; the certificate claimed fineness. Nothing
        # overlaps, so nothing is checked and the fineness claim stands
        # unverified rather than the clay reading inventing a claim to test.
        got = verify(lot_with(grain_fineness=Decimal("58.0")), clay=Percent("9.0"))
        assert got.checked == ()
        assert got.unchecked == ("grain_fineness",)
        assert got.checked_nothing


class TestGuards:
    def test_it_wants_a_lot(self) -> None:
        bad: Any = "L-1"
        with pytest.raises(BadInputError, match="a lot is expected"):
            verify(bad)

    def test_an_unknown_field_lists_the_real_ones(self) -> None:
        with pytest.raises(BadInputError, match="is not on a certificate"):
            verify(lot_with(), stickiness=Decimal(4))

    def test_an_unreadable_measurement_is_refused(self) -> None:
        bad: Any = "58.0"
        with pytest.raises(BadInputError, match="percentage or a decimal"):
            verify(lot_with(grain_fineness=Decimal("58.0")), grain_fineness=bad)

    def test_str_names_the_lot(self) -> None:
        assert str(verify(lot_with())).startswith("lot L-1:")

    def test_a_discrepancy_reads_as_a_sentence(self) -> None:
        got = verify(lot_with(grain_fineness=Decimal("58.0")), grain_fineness=Decimal("70.0"))
        text = str(got.discrepancies[0])
        assert "certificate says 58.0" in text
        assert "the lab reads 70.0" in text
        assert "grain fineness" in text

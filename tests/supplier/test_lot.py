from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from mullerbox.addition.material import Material
from mullerbox.errors import BadInputError, StateError
from mullerbox.supplier.lot import Certificate, Lot, LotState
from mullerbox.units.bulk import Pounds
from mullerbox.units.percent import Percent

DELIVERED = date(2025, 9, 1)


def certificate(number: str = "COA-1", **claims: Any) -> Certificate:
    return Certificate(number=number, **claims)


def lot(state: LotState = LotState.DELIVERED, **extra: Any) -> Lot:
    return Lot(
        lot_id="L-1",
        material=Material.NEW_SAND,
        mass=Pounds.of_tons(24),
        delivered_on=DELIVERED,
        certificate=certificate(grain_fineness=Decimal("58.0")),
        state=state,
        **extra,
    )


class TestCertificate:
    def test_it_needs_a_number(self) -> None:
        with pytest.raises(BadInputError, match="needs a number"):
            certificate(" ")

    def test_a_bare_certificate_is_allowed_and_flagged(self) -> None:
        assert certificate().is_bare
        assert certificate().claims == ()

    def test_it_reports_what_was_actually_filled_in(self) -> None:
        got = certificate(grain_fineness=Decimal("58.0"), clay=Percent("0.3"))
        assert set(got.claims) == {"grain_fineness", "clay"}
        assert not got.is_bare

    def test_the_claims_are_type_checked(self) -> None:
        bad: Any = 58.0
        with pytest.raises(BadInputError, match="claimed fineness is a decimal"):
            certificate(grain_fineness=bad)
        with pytest.raises(BadInputError, match="above zero"):
            certificate(grain_fineness=Decimal(0))
        bad_pct: Any = "0.3"
        with pytest.raises(BadInputError, match="claimed clay is a percentage"):
            certificate(clay=bad_pct)
        with pytest.raises(BadInputError, match="claimed loss on ignition"):
            certificate(loss_on_ignition=bad_pct)


class TestTheStateRunsOneWay:
    def test_a_new_lot_is_delivered_and_unusable(self) -> None:
        assert lot().state is LotState.DELIVERED
        assert not lot().may_be_used

    def test_delivered_then_tested_then_released(self) -> None:
        released = lot().tested().released(by="j.mercer")
        assert released.state is LotState.RELEASED
        assert released.may_be_used
        assert released.released_by == "j.mercer"

    def test_releasing_something_untested_is_refused(self) -> None:
        with pytest.raises(StateError, match="has not been tested"):
            lot().released(by="j.mercer")

    def test_testing_twice_is_refused(self) -> None:
        with pytest.raises(StateError, match="has already been tested"):
            lot().tested().tested()

    def test_a_release_has_to_name_somebody(self) -> None:
        with pytest.raises(BadInputError, match="names who released it"):
            lot().tested().released(by="  ")

    def test_a_released_lot_cannot_be_quarantined(self) -> None:
        released = lot().tested().released(by="j.mercer")
        with pytest.raises(StateError, match="already in the system"):
            released.quarantined("too fine")

    def test_quarantine_works_from_delivered_or_tested(self) -> None:
        assert lot().quarantined("no certificate").state is LotState.QUARANTINED
        assert lot().tested().quarantined("too fine").state is LotState.QUARANTINED

    def test_quarantine_needs_a_reason(self) -> None:
        with pytest.raises(BadInputError, match="names a reason"):
            lot().quarantined("  ")

    def test_the_reason_is_kept(self) -> None:
        assert lot().quarantined("too fine").note == "too fine"

    def test_the_earlier_lot_is_untouched(self) -> None:
        original = lot()
        original.tested()
        assert original.state is LotState.DELIVERED


class TestUsability:
    def test_only_a_released_lot_may_be_used(self) -> None:
        for state in LotState:
            assert LotState.RELEASED.may_be_used or state is not LotState.RELEASED

    def test_requiring_a_usable_lot_names_the_state(self) -> None:
        with pytest.raises(StateError, match="is delivered and cannot go into"):
            lot().require_usable()
        with pytest.raises(StateError, match="is quarantined"):
            lot().quarantined("too fine").require_usable()

    def test_a_released_lot_passes_quietly(self) -> None:
        lot().tested().released(by="j.mercer").require_usable()


class TestConstruction:
    def test_the_pieces_are_checked(self) -> None:
        base: dict[str, Any] = {
            "lot_id": "L-1",
            "material": Material.NEW_SAND,
            "mass": Pounds(100),
            "delivered_on": DELIVERED,
            "certificate": certificate(),
        }
        for field, value, message in [
            ("lot_id", " ", "needs an identifier"),
            ("material", "new sand", "is of a material"),
            ("mass", 100, "lot mass is a bulk mass"),
            ("mass", Pounds.zero(), "nothing in it is not a lot"),
            ("delivered_on", "2025-09-01", "a lot is dated"),
            ("certificate", "COA-1", "carries a certificate"),
        ]:
            kwargs: Any = {**base, field: value}
            with pytest.raises(BadInputError, match=message):
                Lot(**kwargs)

    def test_a_bad_state_is_refused(self) -> None:
        bad: Any = "delivered"
        with pytest.raises(BadInputError, match="a lot has a state"):
            lot(state=bad)

    def test_a_released_lot_built_directly_still_needs_a_name(self) -> None:
        with pytest.raises(BadInputError, match="names who released it"):
            lot(state=LotState.RELEASED)

    def test_every_state_has_a_label(self) -> None:
        assert all(s.label for s in LotState)

    def test_str_names_the_state(self) -> None:
        assert str(lot()) == "lot L-1: 24.000 t of new sand, delivered"

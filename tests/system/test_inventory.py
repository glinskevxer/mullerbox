from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from mullerbox.errors import BadInputError, RuleError
from mullerbox.system.inventory import Count, Vessel, apply_count, reconcile
from mullerbox.system.state import MassBasis, SandSystem
from mullerbox.units.bulk import Pounds
from mullerbox.units.percent import Percent
from mullerbox.units.thermal import Temperature

WHEN = date(2026, 7, 15)
D = Decimal


def vessel(
    name: str = "silo", capacity: str = "1000", fill: str = "0.80", density: str | None = "95"
) -> Vessel:
    return Vessel(
        name=name,
        capacity_cubic_feet=D(capacity),
        filled_fraction=D(fill),
        density_pounds_per_cubic_foot=None if density is None else D(density),
    )


def count(vessels: tuple[Vessel, ...] = (), moulds: int = 0, per: str = "300") -> Count:
    return Count(
        system_name="two",
        counted_on=WHEN,
        vessels=vessels or (vessel(),),
        moulds_standing=moulds,
        sand_per_mould=Pounds(per),
    )


def system(mass: str = "80000", basis: MassBasis = MassBasis.NAMEPLATE) -> SandSystem:
    return SandSystem(
        name="two",
        mass=Pounds(mass),
        basis=basis,
        established_on=date(2026, 1, 5),
        batch_size=Pounds(2000),
        return_temperature=Temperature.fahrenheit(120),
        dust_loss_rate=Percent("1.5"),
    )


class TestAVesselNeedsAMeasuredDensity:
    def test_one_with_a_density_gives_a_mass(self) -> None:
        assert vessel().mass == Pounds(76000)

    def test_one_without_refuses_rather_than_guessing(self) -> None:
        with pytest.raises(RuleError, match="no measured bulk density"):
            _ = vessel(density=None).mass

    def test_and_reports_itself_uncounted(self) -> None:
        assert not vessel(density=None).is_counted
        assert vessel().is_counted

    def test_the_volume_is_still_known(self) -> None:
        assert vessel(density=None).standing_cubic_feet == D("800.00")

    def test_a_negative_density_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="above zero"):
            vessel(density="-1")

    def test_a_density_that_is_not_a_decimal(self) -> None:
        bad: Any = 95.0
        with pytest.raises(BadInputError, match="a bulk density is a decimal"):
            Vessel(
                name="silo",
                capacity_cubic_feet=D(1000),
                filled_fraction=D("0.8"),
                density_pounds_per_cubic_foot=bad,
            )


class TestVesselShape:
    def test_a_vessel_needs_a_name(self) -> None:
        with pytest.raises(BadInputError, match="needs a name"):
            vessel(name="  ")

    def test_one_too_small_to_climb_for(self) -> None:
        with pytest.raises(BadInputError, match="too small to be worth counting"):
            vessel(capacity="4")

    def test_it_cannot_be_more_than_full(self) -> None:
        with pytest.raises(BadInputError, match="cannot be"):
            vessel(fill="1.2")

    def test_an_empty_one_is_allowed(self) -> None:
        assert vessel(fill="0").mass == Pounds(0)

    def test_a_fill_that_is_not_a_decimal(self) -> None:
        bad: Any = 0.8
        with pytest.raises(BadInputError, match="the fill is a decimal"):
            Vessel(
                name="silo",
                capacity_cubic_feet=D(1000),
                filled_fraction=bad,
                density_pounds_per_cubic_foot=D(95),
            )

    def test_str_reads_like_the_clipboard(self) -> None:
        assert str(vessel()) == "silo 80% of 1000 cu ft"


class TestTheFloorIsPartOfTheSystem:
    def test_moulds_standing_are_added(self) -> None:
        got = count(moulds=40, per="300")
        assert got.on_the_floor == Pounds(12000)
        assert got.total == Pounds(88000)

    def test_none_standing_adds_nothing(self) -> None:
        assert count().total == Pounds(76000)

    def test_the_estimated_share_is_reported(self) -> None:
        got = count(moulds=40)
        assert got.floor_share == D("0.136364")

    def test_a_count_of_nothing_has_no_share(self) -> None:
        got = count(vessels=(vessel(fill="0"),))
        assert got.floor_share == D("0.000000")

    def test_moulds_cannot_be_negative(self) -> None:
        with pytest.raises(BadInputError, match="cannot be negative"):
            count(moulds=-1)

    def test_moulds_is_a_whole_number(self) -> None:
        bad: Any = 4.5
        with pytest.raises(BadInputError, match="whole number"):
            count(moulds=bad)


class TestCountShape:
    def test_it_needs_a_vessel(self) -> None:
        with pytest.raises(BadInputError, match="counted nothing"):
            Count(
                system_name="two",
                counted_on=WHEN,
                vessels=(),
                moulds_standing=0,
                sand_per_mould=Pounds(300),
            )

    def test_the_same_vessel_twice(self) -> None:
        with pytest.raises(BadInputError, match="counted twice"):
            count(vessels=(vessel(), vessel()))

    def test_it_needs_a_system(self) -> None:
        with pytest.raises(BadInputError, match="named system"):
            Count(
                system_name=" ",
                counted_on=WHEN,
                vessels=(vessel(),),
                moulds_standing=0,
                sand_per_mould=Pounds(300),
            )

    def test_it_is_dated(self) -> None:
        bad: Any = "2026-07-15"
        with pytest.raises(BadInputError, match="dated"):
            Count(
                system_name="two",
                counted_on=bad,
                vessels=(vessel(),),
                moulds_standing=0,
                sand_per_mould=Pounds(300),
            )

    def test_the_sand_a_mould_takes_is_a_mass(self) -> None:
        bad: Any = 300
        with pytest.raises(BadInputError, match="bulk mass"):
            Count(
                system_name="two",
                counted_on=WHEN,
                vessels=(vessel(),),
                moulds_standing=0,
                sand_per_mould=bad,
            )

    def test_a_partial_count_says_so(self) -> None:
        got = count(vessels=(vessel(), vessel(name="hopper", density=None)))
        assert not got.is_complete
        assert got.uncounted_vessels[0].name == "hopper"
        assert "partial" in str(got)

    def test_a_complete_one_says_so_too(self) -> None:
        assert "complete" in str(count())


class TestReconciling:
    def test_a_count_near_the_figure_reads_as_drift(self) -> None:
        got = reconcile(system("80000"), count())
        assert got.drift == D("-0.0500")
        assert not got.is_suspect

    def test_a_large_shortfall_on_a_partial_count_is_suspect(self) -> None:
        partial = count(vessels=(vessel(fill="0.40"), vessel(name="hopper", density=None)))
        got = reconcile(system("80000"), partial)
        assert got.is_suspect
        assert "too far to be drift" in got.verdict()

    def test_the_same_shortfall_on_a_complete_count_is_believed(self) -> None:
        got = reconcile(system("80000"), count(vessels=(vessel(fill="0.40"),)))
        assert not got.is_suspect
        assert "-52.5%" in got.verdict()

    def test_the_verdict_names_what_was_missed(self) -> None:
        partial = count(vessels=(vessel(), vessel(name="hopper", density=None)))
        assert "hopper had no measured density" in reconcile(system(), partial).verdict()

    def test_it_names_the_basis_it_is_arguing_with(self) -> None:
        assert "nameplate" in reconcile(system(), count()).verdict()
        assert "measured" in reconcile(system(basis=MassBasis.MEASURED), count()).verdict()

    def test_a_count_of_another_system(self) -> None:
        other = Count(
            system_name="one",
            counted_on=WHEN,
            vessels=(vessel(),),
            moulds_standing=0,
            sand_per_mould=Pounds(300),
        )
        with pytest.raises(RuleError, match="this count is of one"):
            reconcile(system(), other)

    def test_it_wants_a_system(self) -> None:
        bad: Any = "two"
        with pytest.raises(BadInputError, match="sand system is expected"):
            reconcile(bad, count())

    def test_it_wants_a_count(self) -> None:
        bad: Any = "count"
        with pytest.raises(BadInputError, match="count is expected"):
            reconcile(system(), bad)

    def test_str_is_the_verdict(self) -> None:
        got = reconcile(system(), count())
        assert str(got) == got.verdict()


class TestAdopting:
    def test_a_complete_count_promotes_the_basis(self) -> None:
        after = apply_count(system(), count())
        assert after.basis is MassBasis.MEASURED
        assert after.mass == Pounds(76000)
        assert after.established_on == WHEN

    def test_a_partial_count_is_not_adopted(self) -> None:
        partial = count(vessels=(vessel(), vessel(name="hopper", density=None)))
        with pytest.raises(RuleError, match="did not reach hopper"):
            apply_count(system(), partial)

    def test_the_system_is_unchanged_by_a_refusal(self) -> None:
        before = system()
        partial = count(vessels=(vessel(), vessel(name="hopper", density=None)))
        with pytest.raises(RuleError):
            apply_count(before, partial)
        assert before.basis is MassBasis.NAMEPLATE

    def test_an_adopted_figure_is_dosable(self) -> None:
        after = apply_count(system(), count())
        assert after.require_trustworthy(WHEN) == Pounds(76000)

    def test_a_count_older_than_the_standing_figure(self) -> None:
        old = Count(
            system_name="two",
            counted_on=date(2025, 1, 1),
            vessels=(vessel(),),
            moulds_standing=0,
            sand_per_mould=Pounds(300),
        )
        with pytest.raises(RuleError, match="already carries a figure"):
            apply_count(system(), old)

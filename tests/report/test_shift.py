from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from mullerbox.errors import BadInputError
from mullerbox.props.kind import PropertyKind
from mullerbox.report.shift import shift_report
from mullerbox.spec.band import Verdict
from mullerbox.spec.pattern import PatternClass
from mullerbox.units.percent import Percent
from mullerbox.units.scales import Permeability
from tests.defect.helpers import readings, spec_for

SHIFT = date(2025, 6, 9)
HEAVY = PatternClass.HEAVY_JOBBING
LIGHT = PatternClass.LIGHT_JOBBING


def report(pattern: PatternClass = HEAVY, **overrides: Any):  # type: ignore[no-untyped-def]
    return shift_report(SHIFT, "number two system", spec_for(pattern), readings(**overrides))


class TestTheClassIsOnTheReport:
    def test_the_heading_names_it(self) -> None:
        assert "judged as heavy jobbing" in report().render()[0]

    def test_one_shift_reads_two_ways(self) -> None:
        wet = {"COMPACTABILITY": Percent("44.5")}
        assert report(HEAVY, **wet).is_clean
        assert not report(PatternClass.THIN_WALL, **wet).is_clean

    def test_the_readings_did_not_change_between_them(self) -> None:
        wet = {"COMPACTABILITY": Percent("44.5")}
        heavy = report(HEAVY, **wet)
        thin = report(PatternClass.THIN_WALL, **wet)
        comp = PropertyKind.COMPACTABILITY
        assert next(x for x in heavy.lines if x.kind is comp).reading == Percent("44.5")
        assert next(x for x in thin.lines if x.kind is comp).reading == Percent("44.5")


class TestUnjudgedPropertiesAreVisible:
    def test_a_property_the_class_does_not_control_still_appears(self) -> None:
        found = {line.kind for line in report(LIGHT).lines}
        assert PropertyKind.LOI in found

    def test_it_carries_a_dash_rather_than_a_verdict(self) -> None:
        line = next(x for x in report(LIGHT).lines if x.kind is PropertyKind.LOI)
        assert not line.is_judged
        assert line.mark == "-"
        assert line.verdict is None

    def test_a_wild_uncontrolled_reading_does_not_make_the_shift_dirty(self) -> None:
        wild = report(LIGHT, LOI=Percent("40"))
        assert wild.is_clean
        assert PropertyKind.LOI in {x.kind for x in wild.unjudged}

    def test_the_footer_names_what_is_not_controlled(self) -> None:
        rendered = "\n".join(report(LIGHT).render())
        assert "not controlled for this work" in rendered
        assert "loss on ignition" in rendered

    def test_no_footer_when_every_reading_is_controlled(self) -> None:
        # No class controls all ten properties, so the case is made by handing
        # over only the readings the class actually holds.
        resolved = spec_for(HEAVY)
        held = {k: v for k, v in readings().items() if resolved.judges(k)}
        got = shift_report(SHIFT, "number two system", resolved, held)
        assert got.unjudged == ()
        assert "not controlled for this work" not in "\n".join(got.render())


class TestVerdicts:
    def test_a_clean_shift_says_so(self) -> None:
        assert "every controlled property is in band" in "\n".join(report().render())

    def test_a_low_reading_is_marked_low(self) -> None:
        got = report(PERMEABILITY=Permeability(40))
        line = next(x for x in got.lines if x.kind is PropertyKind.PERMEABILITY)
        assert line.verdict is Verdict.BELOW
        assert line.mark == "low"

    def test_a_high_reading_is_marked_high(self) -> None:
        got = report(MOISTURE=Percent("9"))
        line = next(x for x in got.lines if x.kind is PropertyKind.MOISTURE)
        assert line.mark == "high"

    def test_the_footer_names_every_excursion(self) -> None:
        got = report(PERMEABILITY=Permeability(40), MOISTURE=Percent("9"))
        rendered = "\n".join(got.render())
        assert "permeability low" in rendered
        assert "moisture high" in rendered
        assert len(got.out_of_band) == 2


class TestTable:
    def test_it_has_a_row_per_reading(self) -> None:
        got = report()
        assert len(got.table()) == len(got.lines)

    def test_the_band_column_drops_the_repeated_property_name(self) -> None:
        got = report()
        line = next(x for x in got.lines if x.kind is PropertyKind.COMPACTABILITY)
        assert not line.band_text.startswith("compactability")
        assert "%" in line.band_text

    def test_the_rows_are_in_a_stable_order(self) -> None:
        first = [x.kind for x in report().lines]
        second = [x.kind for x in report().lines]
        assert first == second == sorted(first, key=lambda k: k.name)

    def test_no_rendered_line_has_trailing_space(self) -> None:
        for line in report().render():
            assert line == line.rstrip()


class TestGuards:
    def test_the_arguments_are_checked(self) -> None:
        bad_spec: Any = "heavy"
        with pytest.raises(BadInputError, match="needs a resolved spec"):
            shift_report(SHIFT, "s", bad_spec, readings())
        bad_date: Any = "2025-06-09"
        with pytest.raises(BadInputError, match="report is dated"):
            shift_report(bad_date, "s", spec_for(HEAVY), readings())
        with pytest.raises(BadInputError, match="names its system"):
            shift_report(SHIFT, "  ", spec_for(HEAVY), readings())

    def test_a_shift_with_no_readings_still_renders(self) -> None:
        empty = shift_report(SHIFT, "s", spec_for(HEAVY), {})
        assert empty.is_clean
        assert empty.lines == ()
        assert empty.render()[0].startswith("s on 2025-06-09")

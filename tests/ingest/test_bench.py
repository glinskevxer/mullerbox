from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from mullerbox.errors import BadInputError, ConfigError
from mullerbox.ingest.bench import BenchLoad, load_bench
from mullerbox.ingest.reader import read_text
from mullerbox.props.kind import PropertyKind
from mullerbox.units.percent import Percent
from mullerbox.units.pressure import Psi
from mullerbox.units.scales import Hardness, Permeability

HEADER = "sample,property,reading,instrument,tested\n"
GOOD = HEADER + (
    "S-100,comp,42.0,RAM-1,2025-05-22\n"
    "S-100,GCS,23.4,USM-1,2025-05-22\n"
    "S-100,perm,110,PERM-1,2025-05-22\n"
    "S-101,H2O,3.2,MOIST-1,2025-05-23\n"
)


def load(text: str = GOOD) -> BenchLoad:
    return load_bench(read_text(text))


class TestTheScaleComesFromTheProperty:
    def test_a_percentage_property(self) -> None:
        got = load().of_property(PropertyKind.COMPACTABILITY)[0]
        assert isinstance(got.reading, Percent)
        assert got.reading == Percent("42.0")

    def test_a_pressure_property(self) -> None:
        got = load().of_property(PropertyKind.GREEN_COMPRESSION)[0]
        assert isinstance(got.reading, Psi)

    def test_a_whole_number_scale(self) -> None:
        got = load().of_property(PropertyKind.PERMEABILITY)[0]
        assert isinstance(got.reading, Permeability)
        assert got.reading == Permeability(110)

    def test_the_same_bare_number_lands_on_two_different_scales(self) -> None:
        text = HEADER + ("S-1,perm,88,PERM-1,2025-05-22\nS-1,hardness,88,USM-1,2025-05-22\n")
        got = load(text)
        by_kind = {r.kind: r.reading for r in got.results}
        assert isinstance(by_kind[PropertyKind.PERMEABILITY], Permeability)
        assert isinstance(by_kind[PropertyKind.MOLD_HARDNESS], Hardness)


class TestParsing:
    def test_a_clean_sheet_loads_whole(self) -> None:
        got = load()
        assert got.is_clean
        assert len(got.results) == 4

    def test_the_shop_shorthand_is_accepted(self) -> None:
        kinds = {r.kind for r in load().results}
        assert PropertyKind.COMPACTABILITY in kinds
        assert PropertyKind.MOISTURE in kinds

    def test_the_date_is_read(self) -> None:
        assert load().results[0].tested_on == date(2025, 5, 22)

    def test_samples_come_back_in_first_appearance_order(self) -> None:
        assert load().samples == ("S-100", "S-101")

    def test_results_can_be_picked_out_by_sample(self) -> None:
        assert len(load().for_sample("S-100")) == 3
        assert load().for_sample("S-999") == ()

    def test_picking_by_property_wants_a_property(self) -> None:
        bad: Any = "comp"
        with pytest.raises(BadInputError, match="property kind is expected"):
            load().of_property(bad)


class TestBadRowsAreKeptRatherThanRaised:
    def test_an_unknown_property_is_one_problem(self) -> None:
        got = load(HEADER + "S-1,stickiness,4,X-1,2025-05-22\nS-2,comp,42,RAM-1,2025-05-22\n")
        assert len(got.results) == 1
        assert len(got.problems) == 1
        assert "not a sand property" in got.problems[0].reason

    def test_a_bad_reading_is_one_problem(self) -> None:
        got = load(HEADER + "S-1,comp,wet,RAM-1,2025-05-22\nS-2,comp,42,RAM-1,2025-05-22\n")
        assert len(got.results) == 1
        assert "is not a percentage" in got.problems[0].reason

    def test_a_bad_date_names_the_format(self) -> None:
        got = load(HEADER + "S-1,comp,42,RAM-1,22/05/2025\n")
        assert "yyyy-mm-dd" in got.problems[0].reason

    def test_an_empty_required_field_is_one_problem(self) -> None:
        got = load(HEADER + "S-1,comp,,RAM-1,2025-05-22\n")
        assert "'reading' is empty" in got.problems[0].reason

    def test_a_reading_off_its_own_scale_is_one_problem(self) -> None:
        got = load(HEADER + "S-1,perm,110.5,PERM-1,2025-05-22\n")
        assert got.results == ()
        assert "permeability" in got.problems[0].reason

    def test_the_problem_carries_its_line(self) -> None:
        got = load(HEADER + "S-1,comp,42,RAM-1,2025-05-22\nS-2,stickiness,4,X-1,2025-05-22\n")
        assert got.problems[0].line == 3

    def test_several_problems_are_all_kept(self) -> None:
        got = load(
            HEADER
            + "S-1,stickiness,4,X-1,2025-05-22\n"
            + "S-2,comp,wet,RAM-1,2025-05-22\n"
            + "S-3,comp,42,RAM-1,2025-05-22\n"
        )
        assert len(got.results) == 1
        assert len(got.problems) == 2


class TestGuards:
    def test_a_missing_column_is_refused_outright(self) -> None:
        with pytest.raises(ConfigError, match="no 'instrument' column"):
            load("sample,property,reading,tested\nS-1,comp,42,2025-05-22\n")

    def test_it_wants_a_parsed_sheet(self) -> None:
        bad: Any = GOOD
        with pytest.raises(BadInputError, match="parsed sheet is expected"):
            load_bench(bad)

    def test_str_summarises_the_load(self) -> None:
        assert str(load()) == "4 results over 2 samples, 0 problems"

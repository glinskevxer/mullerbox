from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from mullerbox.defect.kind import DefectKind
from mullerbox.errors import BadInputError, ConfigError
from mullerbox.heat.heat import Disposition
from mullerbox.ingest.production import (
    InspectionLoad,
    PourLoad,
    load_inspections,
    load_pours,
)
from mullerbox.ingest.reader import read_text
from mullerbox.spec.pattern import PatternClass

POUR_HEADER = "poured,pattern,metal,sand\n"
POURS = POUR_HEADER + (
    "2025-06-02,heavy jobbing,10000,35000\n"
    "2025-06-02,thin wall,4000,32000\n"
    "2025-06-03,heavy_jobbing,9000,31000\n"
)

INSPECT_HEADER = "casting,disposition,defects\n"
INSPECTIONS = INSPECT_HEADER + (
    "C-1,shipped,\nC-2,scrapped,blow\nC-3,scrap,blow;pinhole\nC-4,pending,\n"
)


def pours(text: str = POURS) -> PourLoad:
    return load_pours(read_text(text))


def inspections(text: str = INSPECTIONS) -> InspectionLoad:
    return load_inspections(read_text(text))


class TestPourLog:
    def test_a_clean_log_loads(self) -> None:
        got = pours()
        assert got.is_clean
        assert len(got.pours) == 3

    def test_the_ratio_comes_off_the_file(self) -> None:
        heavy = pours().of(PatternClass.HEAVY_JOBBING)[0]
        assert heavy.sand_to_metal == Decimal("3.50")

    def test_two_classes_on_one_day_stay_separate(self) -> None:
        on_the_second = pours().on(date(2025, 6, 2))
        assert len(on_the_second) == 2
        assert len({p.sand_to_metal for p in on_the_second}) == 2

    def test_the_separators_in_the_class_do_not_matter(self) -> None:
        assert len(pours().of(PatternClass.HEAVY_JOBBING)) == 2

    def test_an_implausible_ratio_still_loads_and_is_caught_later(self) -> None:
        got = pours(POUR_HEADER + "2025-06-02,heavy jobbing,10000,15000\n")
        assert got.is_clean
        with pytest.raises(BadInputError, match="is not a pour record"):
            got.pours[0].require_plausible()

    def test_a_bad_class_is_one_problem(self) -> None:
        got = pours(POUR_HEADER + "2025-06-02,prototype,10000,35000\n")
        assert got.pours == ()
        assert "not a pattern class" in got.problems[0].reason

    def test_a_bad_date_is_one_problem(self) -> None:
        got = pours(POUR_HEADER + "02/06/2025,heavy jobbing,10000,35000\n")
        assert "yyyy-mm-dd" in got.problems[0].reason

    def test_filtering_is_guarded(self) -> None:
        bad: Any = "2025-06-02"
        with pytest.raises(BadInputError, match="a date is expected"):
            pours().on(bad)
        with pytest.raises(BadInputError, match="pattern class is expected"):
            pours().of(bad)


class TestInspectionSheet:
    def test_a_clean_sheet_loads(self) -> None:
        got = inspections()
        assert got.is_clean
        assert len(got.inspections) == 4

    def test_the_dispositions_are_read_in_their_shop_spellings(self) -> None:
        found = {i.casting_id: i.disposition for i in inspections().inspections}
        assert found["C-1"] is Disposition.SHIPPED
        assert found["C-2"] is Disposition.SCRAPPED
        assert found["C-3"] is Disposition.SCRAPPED
        assert found["C-4"] is Disposition.PENDING

    def test_an_empty_disposition_reads_as_pending(self) -> None:
        got = inspections(INSPECT_HEADER + "C-9,,\n")
        assert got.inspections[0].disposition is Disposition.PENDING

    def test_several_defects_are_semicolon_separated(self) -> None:
        by_id = {i.casting_id: i.defects for i in inspections().inspections}
        assert by_id["C-3"] == (DefectKind.BLOW, DefectKind.PINHOLE)

    def test_the_scrap_report_mapping(self) -> None:
        mapping = inspections().defects_by_casting
        assert set(mapping) == {"C-2", "C-3"}
        assert "C-1" not in mapping

    def test_scrapped_castings_are_picked_out(self) -> None:
        assert [i.casting_id for i in inspections().scrapped] == ["C-2", "C-3"]

    def test_a_shipped_casting_with_defects_is_one_problem(self) -> None:
        got = inspections(INSPECT_HEADER + "C-9,shipped,blow\n")
        assert got.inspections == ()
        assert "shipped with 1 defects" in got.problems[0].reason

    def test_an_unknown_defect_is_one_problem(self) -> None:
        got = inspections(INSPECT_HEADER + "C-9,scrapped,ugly\n")
        assert "not a defect on the shop's list" in got.problems[0].reason

    def test_an_unknown_disposition_is_one_problem(self) -> None:
        got = inspections(INSPECT_HEADER + "C-9,maybe,\n")
        assert "not a disposition" in got.problems[0].reason

    def test_a_missing_casting_number_is_one_problem(self) -> None:
        got = inspections(INSPECT_HEADER + ",scrapped,blow\n")
        assert "'casting' is empty" in got.problems[0].reason


class TestGuards:
    def test_missing_columns_are_refused_outright(self) -> None:
        with pytest.raises(ConfigError, match="no 'sand' column"):
            pours("poured,pattern,metal\n2025-06-02,heavy jobbing,10000\n")
        with pytest.raises(ConfigError, match="no 'defects' column"):
            inspections("casting,disposition\nC-1,shipped\n")

    def test_they_want_a_parsed_sheet(self) -> None:
        bad: Any = POURS
        with pytest.raises(BadInputError, match="parsed sheet is expected"):
            load_pours(bad)
        with pytest.raises(BadInputError, match="parsed sheet is expected"):
            load_inspections(bad)

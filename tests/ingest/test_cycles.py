from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from mullerbox.errors import BadInputError, ConfigError
from mullerbox.ingest.cycles import CycleLoad, load_cycles
from mullerbox.ingest.reader import read_text
from mullerbox.units.bulk import Pounds

HEADER = "batch,run,dry,wet,bentonite,water,discharged\n"
GOOD = HEADER + (
    "B-1,2026-03-23,60,120,140,180,yes\n"
    "B-2,2026-03-23,60,120,140,180,y\n"
    "B-3,2026-03-24,60,120,,,1\n"
)


def load(text: str = GOOD) -> CycleLoad:
    return load_cycles(read_text(text))


class TestABlankMassIsZero:
    def test_a_cycle_with_no_additions_reads(self) -> None:
        got = load()
        assert got.is_clean
        bare = got.cycles[2].cycle
        assert bare.bentonite == Pounds.zero()
        assert bare.water == Pounds.zero()

    def test_it_is_not_flagged_as_a_problem(self) -> None:
        assert load().problems == ()

    def test_such_a_cycle_cannot_mull_short(self) -> None:
        assert not load().cycles[2].cycle.mulled_short

    def test_a_missing_column_altogether_still_reads_as_zero(self) -> None:
        thin = "batch,run,dry,wet,discharged\nB-1,2026-03-23,60,120,yes\n"
        got = load(thin)
        assert got.is_clean
        assert got.cycles[0].cycle.water == Pounds.zero()


class TestABlankFlagIsNotAssumed:
    def test_it_is_one_problem(self) -> None:
        got = load(HEADER + "B-9,2026-03-23,60,120,140,180,\n")
        assert got.cycles == ()
        assert len(got.problems) == 1

    def test_the_problem_says_why_guessing_would_be_wrong(self) -> None:
        got = load(HEADER + "B-9,2026-03-23,60,120,140,180,\n")
        assert "does not report it" in got.problems[0].reason

    def test_an_unknown_flag_is_one_problem(self) -> None:
        got = load(HEADER + "B-9,2026-03-23,60,120,140,180,maybe\n")
        assert "is not a discharge flag" in got.problems[0].reason

    @pytest.mark.parametrize("flag", ["yes", "Y", "1", "true", "discharged"])
    def test_the_spellings_that_mean_yes(self, flag: str) -> None:
        got = load(HEADER + f"B-9,2026-03-23,60,120,,,{flag}\n")
        assert got.cycles[0].cycle.discharged

    @pytest.mark.parametrize("flag", ["no", "N", "0", "false", "held", "left"])
    def test_the_spellings_that_mean_no(self, flag: str) -> None:
        got = load(HEADER + f"B-9,2026-03-23,60,120,,,{flag}\n")
        assert not got.cycles[0].cycle.discharged


class TestItKeepsWhatThePlanWouldRefuse:
    def test_a_short_mull_loads(self) -> None:
        got = load(HEADER + "B-9,2026-03-23,60,20,140,180,yes\n")
        assert got.is_clean
        assert got.cycles[0].cycle.mulled_short

    def test_the_history_then_reports_it(self) -> None:
        rows = "".join(f"S-{n},2026-03-23,60,20,140,180,yes\n" for n in range(5))
        got = load(HEADER + rows)
        assert got.history.is_running_short


class TestGrouping:
    def test_the_days_are_listed_in_order(self) -> None:
        assert load().days == (date(2026, 3, 23), date(2026, 3, 24))

    def test_a_day_gathers_its_own_cycles(self) -> None:
        assert len(load().on(date(2026, 3, 23))) == 2

    def test_a_quiet_day_gathers_nothing(self) -> None:
        assert len(load().on(date(2026, 1, 1))) == 0

    def test_the_whole_load_is_one_history(self) -> None:
        assert len(load().history) == 3

    def test_grouping_wants_a_date(self) -> None:
        bad: Any = "2026-03-23"
        with pytest.raises(BadInputError, match="a date is expected"):
            load().on(bad)


class TestGuards:
    def test_a_missing_required_column_is_refused_outright(self) -> None:
        with pytest.raises(ConfigError, match="no 'discharged' column"):
            load("batch,run,dry,wet\nB-1,2026-03-23,60,120\n")

    def test_a_bad_date_names_the_format(self) -> None:
        got = load(HEADER + "B-9,23/03/2026,60,120,,,yes\n")
        assert "yyyy-mm-dd" in got.problems[0].reason

    def test_a_bad_duration_is_one_problem(self) -> None:
        got = load(HEADER + "B-9,2026-03-23,ages,120,,,yes\n")
        assert "is not a duration" in got.problems[0].reason

    def test_it_wants_a_parsed_sheet(self) -> None:
        bad: Any = GOOD
        with pytest.raises(BadInputError, match="parsed sheet is expected"):
            load_cycles(bad)

    def test_str_summarises(self) -> None:
        assert str(load()) == "3 cycles over 2 days, 0 problems"

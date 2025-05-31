from __future__ import annotations

from typing import Any

import pytest

from mullerbox.errors import BadInputError, ConfigError
from mullerbox.gfn.fineness import fineness_of
from mullerbox.ingest.reader import read_text
from mullerbox.ingest.sieve import SieveLoad, load_sieve
from mullerbox.screens.series import AFS_US_SERIES

HEADER = "sample,screen,retained,charged\n"
LABELS = ["6", "12", "20", "30", "40", "50", "70", "100", "140", "200", "270", "PAN"]
MASSES = {
    "50": "8.00",
    "70": "22.00",
    "100": "16.00",
    "140": "4.00",
}


def full_sample(sample_id: str, charged: str = "50.00", skip: str = "") -> str:
    lines = []
    for label in LABELS:
        if label == skip:
            continue
        lines.append(f"{sample_id},{label},{MASSES.get(label, '0.00')},{charged}\n")
    return "".join(lines)


def load(text: str) -> SieveLoad:
    return load_sieve(read_text(text), AFS_US_SERIES)


class TestAssembly:
    def test_a_full_sample_assembles(self) -> None:
        got = load(HEADER + full_sample("S-100"))
        assert got.is_clean
        assert got.samples == ("S-100",)

    def test_the_analysis_is_usable(self) -> None:
        got = load(HEADER + full_sample("S-100"))
        analysis = got.analyses["S-100"]
        assert analysis.closes
        assert fineness_of(analysis).value > 0

    def test_two_samples_in_one_file(self) -> None:
        got = load(HEADER + full_sample("S-100") + full_sample("S-101"))
        assert got.samples == ("S-100", "S-101")

    def test_the_pan_is_read_however_it_is_spelled(self) -> None:
        text = HEADER + full_sample("S-100", skip="PAN") + "S-100,pan.,0.00,50.00\n"
        assert load(text).is_clean


class TestAMissingScreenIsOneProblemPerSample:
    def test_a_short_stack_does_not_assemble(self) -> None:
        got = load(HEADER + full_sample("S-100", skip="140"))
        assert got.analyses == {}
        assert len(got.problems) == 1
        assert "no reading for screen 140" in got.problems[0].reason

    def test_the_problem_names_the_sample(self) -> None:
        got = load(HEADER + full_sample("S-100", skip="140"))
        assert "sample S-100" in got.problems[0].reason

    def test_a_broken_sample_does_not_take_the_others(self) -> None:
        got = load(HEADER + full_sample("S-100", skip="140") + full_sample("S-101"))
        assert got.samples == ("S-101",)
        assert len(got.problems) == 1


class TestOtherFailures:
    def test_a_screen_off_the_series_is_one_problem(self) -> None:
        got = load(HEADER + full_sample("S-100") + "S-100,325,0.10,50.00\n")
        assert any("not on series" in p.reason for p in got.problems)

    def test_two_charged_masses_on_one_sample(self) -> None:
        text = HEADER + full_sample("S-100", skip="140") + "S-100,140,4.00,60.00\n"
        got = load(text)
        assert "different charged masses" in got.problems[0].reason
        assert got.analyses == {}

    def test_a_stack_that_will_not_close_is_one_problem(self) -> None:
        got = load(HEADER + full_sample("S-100", charged="60.00"))
        assert got.analyses == {}
        assert "closure tolerance" in got.problems[0].reason

    def test_a_bad_mass_is_a_row_problem(self) -> None:
        text = HEADER + full_sample("S-100", skip="70") + "S-100,70,heavy,50.00\n"
        got = load(text)
        assert any("is not a mass" in p.reason for p in got.problems)

    def test_problems_come_back_in_line_order(self) -> None:
        text = HEADER + full_sample("S-100", skip="140") + full_sample("S-101", skip="200")
        got = load(text)
        assert [p.line for p in got.problems] == sorted(p.line for p in got.problems)


class TestGuards:
    def test_a_missing_column_is_refused_outright(self) -> None:
        with pytest.raises(ConfigError, match="no 'charged' column"):
            load("sample,screen,retained\nS-1,50,8.00\n")

    def test_it_wants_a_sheet_and_a_series(self) -> None:
        bad: Any = HEADER
        with pytest.raises(BadInputError, match="parsed sheet is expected"):
            load_sieve(bad, AFS_US_SERIES)
        bad_series: Any = "afs"
        with pytest.raises(BadInputError, match="screen series is expected"):
            load_sieve(read_text(HEADER), bad_series)

    def test_str_summarises(self) -> None:
        assert str(load(HEADER + full_sample("S-100"))) == "1 analyses, 0 problems"


class TestClosureIsAskedAtLoadTime:
    def test_a_loaded_analysis_has_already_been_closed(self) -> None:
        """Anything that comes back is safe to derive from without re-checking."""
        got = load(HEADER + full_sample("S-100"))
        for analysis in got.analyses.values():
            analysis.require_closure()
            assert analysis.closes

    def test_the_type_itself_still_builds_a_loose_stack(self) -> None:
        """The check belongs to the loader, not to the constructor."""
        from mullerbox.screens.analysis import SieveAnalysis

        loose = SieveAnalysis.of(
            AFS_US_SERIES,
            "60.00",
            {label: MASSES.get(label, "0.00") for label in LABELS},
        )
        assert not loose.closes

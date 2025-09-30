from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from mullerbox.addition.material import Material
from mullerbox.cal.instrument import InstrumentKind
from mullerbox.cli.parsing import DATE_FORMAT, read_date, read_decimal, read_member
from mullerbox.errors import BadInputError


class TestOneWayToReadADate:
    def test_it_reads_an_iso_date(self) -> None:
        assert read_date("2025-09-24") == date(2025, 9, 24)

    def test_surrounding_space_is_stripped_everywhere(self) -> None:
        assert read_date("  2025-09-24  ") == date(2025, 9, 24)

    def test_the_refusal_names_the_format(self) -> None:
        with pytest.raises(BadInputError, match=DATE_FORMAT):
            read_date("24/09/2025")

    def test_the_refusal_names_what_was_wanted(self) -> None:
        with pytest.raises(BadInputError, match="is not a calibration date"):
            read_date("nonsense", "a calibration date")

    def test_it_wants_text(self) -> None:
        bad: Any = 20250924
        with pytest.raises(BadInputError, match="a date is text"):
            read_date(bad)


class TestReadingANumber:
    def test_it_reads_a_decimal(self) -> None:
        assert read_decimal("58.0", "grain fineness") == Decimal("58.0")

    def test_space_is_stripped(self) -> None:
        assert read_decimal("  58.0 ", "grain fineness") == Decimal("58.0")

    def test_the_refusal_names_the_quantity(self) -> None:
        with pytest.raises(BadInputError, match="is not a grain fineness"):
            read_decimal("fine", "grain fineness")

    def test_it_wants_text(self) -> None:
        bad: Any = 58.0
        with pytest.raises(BadInputError, match="is text on the command line"):
            read_decimal(bad, "grain fineness")


class TestReadingAnEnum:
    def test_the_separators_do_not_matter(self) -> None:
        for spelling in ("sieve shaker", "sieve-shaker", "SIEVE_SHAKER", " Sieve Shaker "):
            got = read_member(spelling, InstrumentKind, "an instrument kind")
            assert got is InstrumentKind.SIEVE_SHAKER

    def test_it_works_for_any_enum(self) -> None:
        assert read_member("new sand", Material, "a material") is Material.NEW_SAND

    def test_the_refusal_lists_the_real_members(self) -> None:
        with pytest.raises(BadInputError, match="permeability") as caught:
            read_member("dowsing rod", InstrumentKind, "an instrument kind")
        assert "is not an instrument kind" in str(caught.value)

    def test_the_list_is_sorted(self) -> None:
        with pytest.raises(BadInputError) as caught:
            read_member("nothing", Material, "a material")
        listed = str(caught.value).split("try ")[1].split(", ")
        assert listed == sorted(listed)

    def test_it_wants_text(self) -> None:
        bad: Any = InstrumentKind.STRENGTH
        with pytest.raises(BadInputError, match="is text on the command line"):
            read_member(bad, InstrumentKind, "an instrument kind")


class TestTheCommandsAllShareIt:
    def test_no_command_module_carries_its_own_date_reader(self) -> None:
        """The six copies are gone and nothing has grown a seventh."""
        import pathlib

        import mullerbox.cli as package

        folder = pathlib.Path(package.__file__).parent
        for module in sorted(folder.glob("*.py")):
            if module.name == "parsing.py":
                continue
            assert "date.fromisoformat" not in module.read_text(), module.name

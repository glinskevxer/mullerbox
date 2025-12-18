from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from mullerbox.errors import BadInputError
from mullerbox.units.percent import Percent
from mullerbox.units.pressure import Psi, WetTensile
from mullerbox.units.reading import SCALES, same_scale, scalar_of
from mullerbox.units.scales import Hardness, Permeability


class TestUnwrapping:
    def test_a_percentage(self) -> None:
        assert scalar_of(Percent("42.00")) == Decimal("42.00")

    def test_a_pressure(self) -> None:
        assert scalar_of(Psi("23.4")) == Decimal("23.4")

    def test_a_wet_tensile(self) -> None:
        assert scalar_of(WetTensile("0.28")) == Decimal("0.28")

    def test_a_hardness(self) -> None:
        assert scalar_of(Hardness(88)) == Decimal("88.0")

    def test_a_permeability_converts_from_its_int(self) -> None:
        got = scalar_of(Permeability(110))
        assert got == Decimal(110)
        assert isinstance(got, Decimal)

    @pytest.mark.parametrize("scale", list(SCALES))
    def test_every_scale_unwraps(self, scale: type) -> None:
        assert isinstance(scalar_of(scale(1)), Decimal)


class TestItRefusesWhatIsNotAReading:
    def test_a_bare_decimal_is_refused(self) -> None:
        bad: Any = Decimal("42")
        with pytest.raises(BadInputError, match="is not a reading"):
            scalar_of(bad)

    def test_a_bare_int_is_refused(self) -> None:
        bad: Any = 42
        with pytest.raises(BadInputError, match="is not a reading"):
            scalar_of(bad)

    def test_the_refusal_names_the_type(self) -> None:
        bad: Any = "42"
        with pytest.raises(BadInputError, match="a str is not a reading"):
            scalar_of(bad)


class TestSameScale:
    def test_two_of_one_scale(self) -> None:
        assert same_scale(Percent(1), Percent(2))

    def test_two_different_scales(self) -> None:
        assert not same_scale(Permeability(88), Hardness(88))

    def test_something_that_is_not_a_reading(self) -> None:
        assert not same_scale(Percent(1), 1)
        assert not same_scale(1, Percent(1))


class TestNobodyReachesForAPrivateCopyAnyMore:
    def test_the_band_module_no_longer_carries_one(self) -> None:
        import mullerbox.spec.band as band

        assert not hasattr(band, "_scalar")

    def test_no_module_imports_a_private_scalar(self) -> None:
        import pathlib

        import mullerbox

        root = pathlib.Path(mullerbox.__file__).resolve().parent
        for path in root.rglob("*.py"):
            assert "import _scalar" not in path.read_text(encoding="utf-8"), path.name

    def test_the_command_modules_use_the_shared_one(self) -> None:
        import mullerbox.cli.programme_cmd as programme
        import mullerbox.cli.reports as reports

        for module in (reports, programme):
            assert module.scalar_of is scalar_of

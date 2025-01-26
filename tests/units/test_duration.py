from __future__ import annotations

from decimal import Decimal

import pytest

from mullerbox.errors import BadInputError
from mullerbox.units.duration import Seconds


class TestConstruction:
    def test_reads_an_int_and_a_string(self) -> None:
        assert Seconds(90) == Seconds("90") == Seconds("90s")

    def test_reads_the_timer_face(self) -> None:
        assert Seconds("2:30") == Seconds(150)

    def test_of_minutes(self) -> None:
        assert Seconds.of_minutes(2) == Seconds(120)

    def test_of_minutes_wants_a_whole_number(self) -> None:
        with pytest.raises(BadInputError, match="whole number"):
            Seconds.of_minutes(1.5)
        with pytest.raises(BadInputError, match="whole number"):
            Seconds.of_minutes(True)

    def test_a_bad_timer_face_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="sixty seconds in a minute"):
            Seconds("2:75")
        with pytest.raises(BadInputError, match="is not a duration"):
            Seconds("2:30:15")
        with pytest.raises(BadInputError, match="is not a duration"):
            Seconds("two:thirty")

    def test_negative_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="cannot be negative"):
            Seconds(-1)

    def test_a_jammed_timer_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="longer than any muller cycle"):
            Seconds(1801)

    def test_unreadable_values_are_refused(self) -> None:
        with pytest.raises(BadInputError, match="is not a duration"):
            Seconds("ninety")
        with pytest.raises(BadInputError, match="cannot read a duration"):
            Seconds(None)
        with pytest.raises(BadInputError, match="from a boolean"):
            Seconds(True)

    def test_a_duration_reads_back_from_a_duration(self) -> None:
        assert Seconds(Seconds(90)) == Seconds(90)


class TestArithmetic:
    def test_addition(self) -> None:
        assert Seconds(30) + Seconds(90) == Seconds(120)

    def test_subtraction_refuses_to_go_negative(self) -> None:
        with pytest.raises(BadInputError, match="negative duration"):
            Seconds(30) - Seconds(90)

    def test_subtraction(self) -> None:
        assert Seconds(120) - Seconds(30) == Seconds(90)

    def test_arithmetic_against_another_type_is_not_implemented(self) -> None:
        with pytest.raises(TypeError):
            Seconds(1) + 1
        with pytest.raises(TypeError):
            Seconds(1) - 1


class TestPresentation:
    def test_minutes(self) -> None:
        assert Seconds(90).minutes == Decimal("1.50")

    def test_str_under_a_minute(self) -> None:
        assert str(Seconds(45)) == "45s"

    def test_str_over_a_minute_pads_the_seconds(self) -> None:
        assert str(Seconds(90)) == "1:30"
        assert str(Seconds(125)) == "2:05"

    def test_zero(self) -> None:
        assert Seconds.zero().is_zero
        assert Seconds().is_zero

    def test_orders_and_hashes(self) -> None:
        assert Seconds(30) < Seconds(90)
        assert len({Seconds(90), Seconds("90")}) == 1

    def test_unequal_against_another_type(self) -> None:
        assert Seconds(90) != 90

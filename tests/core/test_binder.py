from __future__ import annotations

from decimal import Decimal

import pytest

from mullerbox.core.binder import Binder, BinderSystem
from mullerbox.errors import BadInputError
from mullerbox.units.duration import Seconds
from mullerbox.units.percent import Percent
from mullerbox.units.pressure import Psi


def system(
    binder: Binder = Binder.PHENOLIC_URETHANE,
    resin: str = "1.2",
    catalyst: str = "0.06",
    bench: int = 300,
    strip: int = 120,
    cure: int = 900,
) -> BinderSystem:
    return BinderSystem(
        binder=binder,
        resin=Percent(resin),
        catalyst=Percent(catalyst),
        bench_life=Seconds(bench),
        strip_time=Seconds(strip),
        full_cure=Seconds(cure),
        tensile_floor=Psi(180),
    )


class TestBinders:
    @pytest.mark.parametrize("binder", list(Binder))
    def test_every_binder_has_a_label(self, binder: Binder) -> None:
        assert binder.label.strip()

    def test_only_shell_is_heat_cured(self) -> None:
        hot = [b for b in Binder if b.is_heat_cured]
        assert hot == [Binder.SHELL]

    def test_only_silicate_does_not_gas(self) -> None:
        quiet = [b for b in Binder if not b.gasses_on_pour]
        assert quiet == [Binder.SODIUM_SILICATE]


class TestTheClockRunsInOrder:
    def test_strip_before_bench_life(self) -> None:
        with pytest.raises(BadInputError, match="dies before the core can be drawn"):
            system(bench=100, strip=120)

    def test_strip_equal_to_bench_life_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="dies before the core"):
            system(bench=120, strip=120)

    def test_cure_after_strip(self) -> None:
        with pytest.raises(BadInputError, match="which is not after its strip time"):
            system(strip=200, cure=200)

    def test_a_sensible_system_builds(self) -> None:
        assert system().strip_time < system().bench_life < system().full_cure


class TestTheWindows:
    def test_sand_is_workable_until_bench_life(self) -> None:
        built = system(bench=300)
        assert built.is_workable_at(Seconds(299))
        assert not built.is_workable_at(Seconds(300))

    def test_a_core_may_strip_from_its_strip_time(self) -> None:
        built = system(strip=120)
        assert not built.may_strip_at(Seconds(119))
        assert built.may_strip_at(Seconds(120))

    def test_a_core_is_cured_from_its_cure_time(self) -> None:
        built = system(cure=900)
        assert not built.is_cured_at(Seconds(899))
        assert built.is_cured_at(Seconds(900))

    def test_the_fragile_window_is_between_strip_and_cure(self) -> None:
        assert system(strip=120, cure=900).fragile_window == Seconds(780)

    def test_the_windows_want_a_duration(self) -> None:
        built = system()
        for check in (built.is_workable_at, built.may_strip_at, built.is_cured_at):
            with pytest.raises(BadInputError, match="an age is a duration"):
                check(120)  # type: ignore[arg-type]


class TestTheAdditions:
    def test_the_total_is_resin_plus_catalyst(self) -> None:
        assert system(resin="1.2", catalyst="0.06").total_binder == Percent("1.26")

    def test_the_catalyst_ratio_is_what_the_supplier_quotes(self) -> None:
        assert system(resin="1.2", catalyst="0.06").catalyst_ratio == Decimal("0.050")

    def test_no_resin_is_refused(self) -> None:
        with pytest.raises(BadInputError, match="no resin is not a binder system"):
            system(resin="0")


class TestGuards:
    def test_the_pieces_are_checked(self) -> None:
        with pytest.raises(BadInputError, match="names a binder"):
            BinderSystem(
                binder="furan",  # type: ignore[arg-type]
                resin=Percent("1.2"),
                catalyst=Percent("0.06"),
                bench_life=Seconds(300),
                strip_time=Seconds(120),
                full_cure=Seconds(900),
                tensile_floor=Psi(180),
            )
        with pytest.raises(BadInputError, match="resin addition is a percentage"):
            BinderSystem(
                binder=Binder.FURAN,
                resin="1.2",  # type: ignore[arg-type]
                catalyst=Percent("0.06"),
                bench_life=Seconds(300),
                strip_time=Seconds(120),
                full_cure=Seconds(900),
                tensile_floor=Psi(180),
            )
        with pytest.raises(BadInputError, match="bench life is a duration"):
            BinderSystem(
                binder=Binder.FURAN,
                resin=Percent("1.2"),
                catalyst=Percent("0.06"),
                bench_life=300,  # type: ignore[arg-type]
                strip_time=Seconds(120),
                full_cure=Seconds(900),
                tensile_floor=Psi(180),
            )
        with pytest.raises(BadInputError, match="tensile floor is a pressure"):
            BinderSystem(
                binder=Binder.FURAN,
                resin=Percent("1.2"),
                catalyst=Percent("0.06"),
                bench_life=Seconds(300),
                strip_time=Seconds(120),
                full_cure=Seconds(900),
                tensile_floor=180,  # type: ignore[arg-type]
            )

    def test_str_names_the_binder_and_the_bench_life(self) -> None:
        assert str(system()) == ("phenolic urethane no bake at 1.20% resin, bench life 5:00")

from __future__ import annotations

import pytest

from mullerbox.errors import BadInputError
from mullerbox.screens.series import AFS_US_SERIES, ScreenSeries, Step
from mullerbox.units.mesh import Mesh


def series_of(*pairs: tuple[Mesh, int], name: str = "test") -> ScreenSeries:
    return ScreenSeries(name=name, steps=tuple(Step(m, w) for m, w in pairs))


class TestStep:
    def test_a_step_wants_a_screen(self) -> None:
        with pytest.raises(BadInputError, match="built on a screen"):
            Step(50, 40)  # type: ignore[arg-type]

    def test_a_multiplier_is_a_whole_number_above_zero(self) -> None:
        with pytest.raises(BadInputError, match="whole number"):
            Step(Mesh(50, 300), 40.0)  # type: ignore[arg-type]
        with pytest.raises(BadInputError, match="whole number"):
            Step(Mesh(50, 300), True)
        with pytest.raises(BadInputError, match="above zero"):
            Step(Mesh(50, 300), 0)

    def test_label_comes_off_the_screen(self) -> None:
        assert Step(Mesh(50, 300), 40).label == "50"
        assert Step(Mesh.pan(), 300).label == "PAN"


class TestSeriesConstruction:
    def test_a_series_needs_a_name(self) -> None:
        with pytest.raises(BadInputError, match="needs a name"):
            series_of((Mesh(50, 300), 40), (Mesh.pan(), 300), name="  ")

    def test_a_series_needs_a_screen_and_a_pan(self) -> None:
        with pytest.raises(BadInputError, match="at least one screen and a pan"):
            ScreenSeries(name="short", steps=(Step(Mesh.pan(), 300),))

    def test_a_series_ends_at_the_pan(self) -> None:
        with pytest.raises(BadInputError, match="ends at the pan"):
            series_of((Mesh(30, 600), 20), (Mesh(50, 300), 40))

    def test_only_the_last_step_is_the_pan(self) -> None:
        with pytest.raises(BadInputError, match="only the last step"):
            series_of((Mesh.pan(), 20), (Mesh(50, 300), 40), (Mesh.pan(), 300))

    def test_screens_have_to_be_stacked_coarse_first(self) -> None:
        with pytest.raises(BadInputError, match="does not sit under"):
            series_of((Mesh(50, 300), 20), (Mesh(30, 600), 40), (Mesh.pan(), 300))

    def test_multipliers_rise_towards_the_fine_end(self) -> None:
        with pytest.raises(BadInputError, match="rise from coarse to fine"):
            series_of((Mesh(30, 600), 40), (Mesh(50, 300), 20), (Mesh.pan(), 300))

    def test_two_screens_cannot_share_a_multiplier(self) -> None:
        with pytest.raises(BadInputError, match="same multiplier"):
            series_of((Mesh(30, 600), 20), (Mesh(50, 300), 20), (Mesh.pan(), 300))


class TestTheAfsSeries:
    def test_it_has_twelve_steps_ending_at_the_pan(self) -> None:
        assert len(AFS_US_SERIES) == 12
        assert AFS_US_SERIES.pan.mesh.is_pan

    def test_the_labels_read_coarse_to_fine(self) -> None:
        assert AFS_US_SERIES.labels == (
            "6",
            "12",
            "20",
            "30",
            "40",
            "50",
            "70",
            "100",
            "140",
            "200",
            "270",
            "PAN",
        )

    def test_the_published_multipliers(self) -> None:
        assert [s.multiplier for s in AFS_US_SERIES.steps] == [
            3,
            5,
            10,
            20,
            30,
            40,
            50,
            70,
            100,
            140,
            200,
            300,
        ]

    def test_working_steps_leave_the_pan_out(self) -> None:
        assert len(AFS_US_SERIES.working_steps) == 11
        assert not any(s.mesh.is_pan for s in AFS_US_SERIES.working_steps)

    def test_meshes_are_in_stack_order(self) -> None:
        assert list(AFS_US_SERIES.meshes) == sorted(AFS_US_SERIES.meshes)


class TestLookup:
    def test_a_multiplier_comes_back_by_screen(self) -> None:
        assert AFS_US_SERIES.multiplier_for(Mesh(50, 300)) == 40

    def test_a_position_counts_from_the_coarse_end(self) -> None:
        assert AFS_US_SERIES.position_of(Mesh(6, 3350)) == 0
        assert AFS_US_SERIES.position_of(Mesh.pan()) == 11

    def test_a_screen_from_another_series_is_refused(self) -> None:
        foreign = Mesh(50, 297)
        assert not AFS_US_SERIES.contains(foreign)
        with pytest.raises(BadInputError, match="is not on series"):
            AFS_US_SERIES.multiplier_for(foreign)
        with pytest.raises(BadInputError, match="is not on series"):
            AFS_US_SERIES.position_of(foreign)

    def test_indexing_wants_a_screen(self) -> None:
        with pytest.raises(BadInputError, match="indexed by a screen"):
            AFS_US_SERIES.step_for(50)  # type: ignore[arg-type]

    def test_contains(self) -> None:
        assert AFS_US_SERIES.contains(Mesh(70, 212))
        assert AFS_US_SERIES.contains(Mesh.pan())

from __future__ import annotations

from typing import Any

import pytest

from mullerbox.addition.material import Material
from mullerbox.cal.instrument import InstrumentKind
from mullerbox.errors import BadInputError
from mullerbox.props.kind import PropertyKind
from mullerbox.store.coding import decode, decode_optional, encode
from mullerbox.supplier.lot import LotState


class TestEncoding:
    def test_it_stores_the_name_not_the_label(self) -> None:
        assert encode(Material.NEW_SAND) == "NEW_SAND"
        assert encode(Material.NEW_SAND) != Material.NEW_SAND.value

    def test_it_round_trips(self) -> None:
        for member in Material:
            assert decode(encode(member), Material, "a material") is member

    def test_it_wants_an_enum(self) -> None:
        bad: Any = "NEW_SAND"
        with pytest.raises(BadInputError, match="only enum members"):
            encode(bad)


class TestDecoding:
    def test_a_good_name(self) -> None:
        assert decode("RELEASED", LotState, "a lot state") is LotState.RELEASED
        assert decode("QUARANTINED", LotState, "a lot state") is LotState.QUARANTINED

    def test_it_works_for_any_enum(self) -> None:
        assert decode("MUFFLE", InstrumentKind, "an instrument kind") is (InstrumentKind.MUFFLE)
        assert decode("LOI", PropertyKind, "a property") is PropertyKind.LOI


class TestTheRefusalIsTheSameEverywhere:
    def test_it_names_what_was_stored(self) -> None:
        with pytest.raises(BadInputError, match="carries 'GRAVEL'"):
            decode("GRAVEL", Material, "a material")

    def test_it_names_the_enum_in_the_shop_s_words(self) -> None:
        with pytest.raises(BadInputError, match="as a material"):
            decode("GRAVEL", Material, "a material")

    def test_it_lists_the_real_members(self) -> None:
        with pytest.raises(BadInputError, match="BENTONITE"):
            decode("GRAVEL", Material, "a material")

    def test_the_list_is_sorted(self) -> None:
        with pytest.raises(BadInputError) as caught:
            decode("GRAVEL", Material, "a material")
        listed = str(caught.value).split("which is not one of ")[1].split(", ")
        assert listed == sorted(listed)

    def test_a_non_string_is_refused_differently(self) -> None:
        bad: Any = 3
        with pytest.raises(BadInputError, match="which is not text"):
            decode(bad, Material, "a material")

    def test_every_repository_now_says_the_same_thing(self) -> None:
        """One sentence shape, whichever table the corruption is in."""
        shapes = []
        for members, what in (
            (Material, "a material"),
            (LotState, "a lot state"),
            (PropertyKind, "a property"),
            (InstrumentKind, "an instrument kind"),
        ):
            with pytest.raises(BadInputError) as caught:
                decode("NONSENSE", members, what)
            shapes.append(str(caught.value).split("'NONSENSE'")[1].split(",")[0])
        assert shapes == [
            f" as {w}" for w in ("a material", "a lot state", "a property", "an instrument kind")
        ]


class TestOptional:
    def test_a_null_comes_back_as_nothing(self) -> None:
        assert decode_optional(None, Material, "a material") is None

    def test_a_name_still_decodes(self) -> None:
        assert decode_optional("WATER", Material, "a material") is Material.WATER

    def test_a_bad_name_is_still_refused(self) -> None:
        with pytest.raises(BadInputError, match="which is not one of"):
            decode_optional("GRAVEL", Material, "a material")


class TestNobodyHasTheirOwnDecoderAnyMore:
    def test_no_store_module_indexes_an_enum_directly(self) -> None:
        import pathlib

        import mullerbox.store as store

        folder = pathlib.Path(store.__file__).parent
        for path in sorted(folder.glob("*_repo.py")):
            text = path.read_text(encoding="utf-8")
            assert "except KeyError" not in text, path.name

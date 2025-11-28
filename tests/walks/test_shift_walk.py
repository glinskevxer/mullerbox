"""A whole shift, driven through the command line the way the shop would.

Every other test in this suite exercises one layer. This one exercises the
seams between them, which is where the interesting failures live: a repository
that stores something the report cannot read back, a command that builds an
object the next command refuses, a spec resolved for the wrong class.

It is deliberately one long walk rather than several short ones. The point is
the ordering: the sand is sampled before it is judged, the pour is recorded
before the muller is planned against it, and the heat is recorded before its
scrap is charged. A test that set each stage up independently would pass with
the ordering broken.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.cli.helpers import initialised, run

SHIFT = "2025-12-01"
LABELS = ["6", "12", "20", "30", "40", "50", "70", "100", "140", "200", "270", "PAN"]
SIEVE_MASSES = {"50": "8.00", "70": "22.00", "100": "16.00", "140": "4.00"}


def sieve_csv(sample_id: str) -> str:
    rows = "".join(
        f"{sample_id},{label},{SIEVE_MASSES.get(label, '0.00')},50.00\n" for label in LABELS
    )
    return "sample,screen,retained,charged\n" + rows


@pytest.fixture
def shop(tmp_path: Path) -> Path:
    """A book with the catalogue, the spec and the prices already on it."""
    book = initialised(tmp_path)
    assert run("catalogue", "load-afs", book=book).exit_code == 0
    for tag, kind in (
        ("RAM-1", "compactability"),
        ("USM-1", "strength"),
        ("PERM-1", "permeability"),
        ("MOIST-1", "moisture"),
        ("CLAY-1", "clay"),
        ("MUF-1", "muffle"),
    ):
        assert run("catalogue", "instrument-add", tag, kind, book=book).exit_code == 0
        assert (
            run(
                "catalogue",
                "calibrate",
                tag,
                f"C-{tag}",
                "--on",
                "2025-01-06",
                "--days",
                "400",
                book=book,
            ).exit_code
            == 0
        )
    assert run("spec", "load-default", "--on", "2025-01-06", book=book).exit_code == 0
    for material, rate in (
        ("bentonite", "142.00"),
        ("seacoal", "196.50"),
        ("new sand", "38.25"),
        ("water", "0"),
    ):
        assert (
            run("cost", "set-price", material, rate, "--from", "2025-01-06", book=book).exit_code
            == 0
        )
    return book


class TestAWholeShift:
    def test_the_walk_runs_end_to_end(self, shop: Path, tmp_path: Path) -> None:
        book = shop

        # The lab pulls a sample and runs the bench.
        assert (
            run(
                "lab",
                "sample-add",
                "S-1",
                "--on",
                SHIFT,
                "--point",
                "muller discharge",
                "--system",
                "number two",
                book=book,
            ).exit_code
            == 0
        )
        for kind, reading, tag in (
            ("comp", "38", "RAM-1"),
            ("gcs", "23", "USM-1"),
            ("perm", "110", "PERM-1"),
            ("h2o", "3.2", "MOIST-1"),
            ("mb", "7.5", "CLAY-1"),
            ("loi", "2.4", "MUF-1"),
        ):
            got = run(
                "lab",
                "result-add",
                "S-1",
                kind,
                reading,
                "--instrument",
                tag,
                "--on",
                SHIFT,
                book=book,
            )
            assert got.exit_code == 0, got.output

        # The shaker export goes on against the series already loaded.
        path = tmp_path / "sieve.csv"
        path.write_text(sieve_csv("S-1"), encoding="utf-8")
        loaded = run("import", "sieve", str(path), "--series", "AFS US 11 screen", book=book)
        assert loaded.exit_code == 0
        assert "loaded 1 analyses" in loaded.output

        # The fineness reads back off what was stored.
        fineness = run("lab", "fineness", "S-1", book=book)
        assert fineness.exit_code == 0
        assert "GFN" in fineness.output

        # The pour log arrives and the muller is planned against it.
        pours = tmp_path / "pours.csv"
        pours.write_text(
            f"poured,pattern,metal,sand\n{SHIFT},medium jobbing,10000,60000\n",
            encoding="utf-8",
        )
        assert run("import", "pours", str(pours), book=book).exit_code == 0
        plan = run(
            "muller",
            "plan",
            "--on",
            SHIFT,
            "--pattern",
            "medium jobbing",
            "--system",
            "300000",
            "--batch",
            "6000",
            "--mb",
            "7.5",
            "--mb-target",
            "8.0",
            "--loi",
            "2.4",
            "--loi-ceiling",
            "3.5",
            "--total-clay",
            "10.5",
            "--dead-target",
            "2.0",
            "--losses",
            "2000",
            "--comp",
            "38",
            "--comp-target",
            "42",
            "--return-f",
            "118",
            book=book,
        )
        assert plan.exit_code == 0, plan.output
        assert "bentonite" in plan.output
        assert "bond projected from" in plan.output

        # The shift report judges the same sand two ways.
        heavy = run("report", "shift", "heavy jobbing", "--on", SHIFT, book=book)
        thin = run("report", "shift", "thin wall", "--on", SHIFT, book=book)
        assert heavy.exit_code == thin.exit_code == 0
        assert "judged as heavy jobbing" in heavy.output
        assert "judged as thin wall" in thin.output

        # The heat is recorded and its scrap charged.
        assert (
            run(
                "production",
                "record-heat",
                "H-1",
                "--on",
                SHIFT,
                "--mold",
                "M-1:medium jobbing:700",
                "--casting",
                "C-1:M-1:200:scrapped",
                "--casting",
                "C-2:M-1:9800:shipped",
                book=book,
            ).exit_code
            == 0
        )
        inspections = tmp_path / "insp.csv"
        inspections.write_text("casting,disposition,defects\nC-1,scrapped,blow\n", encoding="utf-8")
        scrap = run("production", "scrap", "H-1", "--inspections", str(inspections), book=book)
        assert scrap.exit_code == 0, scrap.output
        assert "scrap on heat H-1" in scrap.output

        # And the shift is costed against the good iron it actually made.
        cost = run(
            "cost",
            "shift",
            "--on",
            SHIFT,
            "--bentonite",
            "2000",
            "--new-sand",
            "4000",
            book=book,
        )
        assert cost.exit_code == 0, cost.output
        assert "from the heats on the book" in cost.output
        assert "per ton of good iron" in cost.output


class TestTheOrderingIsLoadBearing:
    def test_a_reading_cannot_be_added_before_its_sample(self, shop: Path) -> None:
        got = run(
            "lab",
            "result-add",
            "S-9",
            "comp",
            "42",
            "--instrument",
            "RAM-1",
            "--on",
            SHIFT,
            book=shop,
        )
        assert got.exit_code != 0

    def test_the_muller_cannot_be_planned_before_the_pour_log(self, shop: Path) -> None:
        got = run(
            "muller",
            "plan",
            "--on",
            SHIFT,
            "--pattern",
            "medium jobbing",
            "--system",
            "300000",
            "--batch",
            "6000",
            "--mb",
            "7.5",
            "--mb-target",
            "8.0",
            "--loi",
            "2.4",
            "--loi-ceiling",
            "3.5",
            "--total-clay",
            "10.5",
            "--dead-target",
            "2.0",
            "--losses",
            "2000",
            "--comp",
            "38",
            "--comp-target",
            "42",
            "--return-f",
            "118",
            book=shop,
        )
        assert got.exit_code != 0
        assert "pour record on" in got.output

    def test_scrap_cannot_be_charged_before_the_heat(self, shop: Path) -> None:
        got = run("production", "scrap", "H-1", book=shop)
        assert got.exit_code != 0

    def test_a_sieve_export_cannot_load_before_its_sample(self, shop: Path, tmp_path: Path) -> None:
        path = tmp_path / "sieve.csv"
        path.write_text(sieve_csv("S-99"), encoding="utf-8")
        got = run("import", "sieve", str(path), "--series", "AFS US 11 screen", book=shop)
        assert "is not on the book" in got.output
        assert "loaded 0 analyses" in got.output

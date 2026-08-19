# mullerbox

Green sand control for a grey iron jobbing foundry.

The sand in a green sand foundry goes round in a loop: it comes off shakeout
hot and burnt, gets returned to the muller, gets new sand, bentonite, seacoal
and water added, gets mulled, and goes back to the molding line. The lab pulls
samples off it and runs the AFS property tests. Those numbers decide the next
batch's additions, and when castings come back scrapped the lab has to say
whether the sand caused it.

This package is the book that holds all of that.

## What it does

- **Sieve analysis and grain fineness**, with the distribution kept attached to
  the number, because two completely different sands average the same GFN.
- **The AFS property tests** — compactability, green compression, permeability,
  moisture, methylene blue clay, total clay, LOI, volatiles, friability, wet
  tensile, mold hardness, shatter index — each tied to the instrument that
  measures it and the scale it reads in.
- **Calibration windows** on those instruments. A result counts only if its
  instrument was in calibration on the day the test ran, and that is recomputed
  every time it is asked rather than stored.
- **Spec bands resolved against the pattern class on the line.** The same
  reading is in band for heavy jobbing work and out of band for thin wall, and
  neither answer is the answer.
- **The muller additions** — bentonite, seacoal, new sand and temper water —
  worked out in the order they depend on each other, with the water sized
  against the bond the batch will have rather than the bond it has.
- **Defect attribution.** A scrapped casting is charged to the sand only when
  the pattern class allows that defect to be sand's fault *and* a property that
  could cause it was out of the band in force at molding time.
- **Control charts, capability and trend**, read together, because each one
  alone gets the diagnosis wrong about half the time.
- **Core sand** on its own clock: bench life, strip time and full cure.
- **Incoming material**, with the supplier's claims kept separate from the
  lab's own readings and a release that names who released it.

## Getting started

```
pip install -e ".[dev]"
mullerbox init
mullerbox catalogue load-afs
mullerbox spec load-default --on 2025-01-06
mullerbox doctor
```

`mullerbox doctor` walks the whole book and prints what is wrong with it,
ranked by what each finding is costing right now. On a healthy book it prints
one line.

## Command groups

| group | what it covers |
| --- | --- |
| `bench` | specimens and the published test methods |
| `catalogue` | screen series and lab instruments |
| `core` | binder systems, core batches, tensiles |
| `cost` | material prices, shift cost, budget variance |
| `export` | writing the book back out as csv |
| `import` | loading the shop's csv exports, including screen calibration |
| `lab` | samples, readings, duplicates and cross checks |
| `material` | incoming lots and their release |
| `muller` | batch planning, the charge order, the muller's own log |
| `pattern` | the pattern register and pour record checks |
| `production` | heats, scrap, Pareto and yields |
| `programme` | how often each property is tested |
| `report` | shift, exceptions, charts, analysis, what is due |
| `screens` | sieve wear and stack fitness |
| `spec` | published sheets and what a revision changes |
| `system` | mass, balance, inventory counts, cooler, dust collector |

## How it is put together

`units` and `model` know nothing about storage. `store` knows nothing about the
shop's rules. The rule modules take model objects in and give model objects
back, and the command layer is the only thing that knows about both a book and a
terminal.

Three habits run through the whole package and are worth knowing before reading
any of it:

**A question about a moment takes the moment as an argument.** Nothing reads the
clock inside itself, so every answer can be replayed off a record and tested at
its boundary.

**Derived things are derived at the point of asking.** Resolved spec bands are
never stored, because a stored one goes stale silently the day the sheet is
revised.

**What was planned and what happened are different records.** The muller cycle
that was planned is validated; the one the machine logged is not, because a
short mull is the observation rather than an error.

## Running the checks

```
ruff check . && ruff format --check .
mypy
pytest -q --cov --cov-fail-under=95
python -m mullerbox.tools.check_exports
python -m mullerbox.tools.check_migrations
python -m mullerbox.tools.check_docstrings
python -m mullerbox.tools.check_workflow
python -m mullerbox.tools.check_release
```

The gates in `mullerbox.tools` check things the test suite cannot: that every
module's `__all__` tells the truth, that no shipped migration has been edited,
that the public surface is documented, that CI runs every gate, and that the
release surface holds. `check_workflow` is the one that stops a gate being
written and never wired up.

CI runs all of it on Python 3.12 and 3.13, then builds the wheel and installs it
into a clean environment.

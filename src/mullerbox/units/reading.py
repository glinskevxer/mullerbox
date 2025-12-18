"""Getting the bare number out of a reading, in one place.

Every scale in this package wraps a number and refuses to be confused with the
other scales, which is the point of them. Some things genuinely need the number
underneath: a control chart is arithmetic on a sequence and does not care what
the sequence measures, and a band comparison has to put two readings on the same
axis before it can order them.

That escape hatch existed five times over. ``spec.band`` had a private
``_scalar`` that three other modules reached across a package boundary to
import, and two command modules had grown their own copies with slightly
different refusals. Reaching for another module's underscore is the smell that
says the thing being reached for should not be private.

So it is public and it lives with the scales rather than with the bands, because
it is a fact about a reading and not about a specification. ``Permeability``
carries an ``int`` and everything else carries a ``Decimal``, so the conversion
is here too rather than at each of the five call sites that used to guess.
"""

from __future__ import annotations

from decimal import Decimal

from mullerbox.errors import BadInputError
from mullerbox.units.percent import Percent
from mullerbox.units.pressure import Psi, WetTensile
from mullerbox.units.scales import Hardness, Permeability

# Everything a reading can be. Kept beside the function that unwraps them so
# that adding a scale and forgetting to unwrap it is one edit, not two.
SCALES = (Percent, Psi, WetTensile, Permeability, Hardness)


def scalar_of(reading: object) -> Decimal:
    """The bare number behind any reading.

    Refuses anything that is not one of the package's scales, including a bare
    ``Decimal``. A caller holding a plain number does not need this and a caller
    that thinks it holds a reading and does not should be told.
    """
    if not isinstance(reading, SCALES):
        raise BadInputError(
            f"a {type(reading).__name__} is not a reading on any of this package's scales"
        )
    value = reading.value
    return Decimal(value) if isinstance(value, int) else value


def same_scale(first: object, second: object) -> bool:
    """Whether two readings are on the same scale and can be compared."""
    return isinstance(first, SCALES) and isinstance(second, SCALES) and type(first) is type(second)


__all__ = ["SCALES", "same_scale", "scalar_of"]

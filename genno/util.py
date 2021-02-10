import logging
from functools import partial
from inspect import Parameter, signature

import pandas as pd
import pint
from dask.core import literal

from .core.key import Key

log = logging.getLogger(__name__)


#: Replacements to apply to Quantity units before parsing by
#: :doc:`pint <pint:index>`. Mapping from original unit -> preferred unit.
#:
#: The default values include:
#:
#: - The '%' symbol cannot be supported by pint, because it is a Python operator; it is
#:   replaced with “percent”.
#:
#: Additional values can be added with :meth:`configure`; see :ref:`config-units`.
REPLACE_UNITS = {
    "%": "percent",
}


def clean_units(input_string):
    """Tolerate messy strings for units.

    - Dimensions enclosed in “[]” have these characters stripped.
    - Replacements from :data:`.REPLACE_UNITS` are applied.
    """
    input_string = input_string.strip("[]")
    for old, new in REPLACE_UNITS.items():
        input_string = input_string.replace(old, new)
    return input_string


def collect_units(*args):
    """Return the "_unit" attributes of the *args*."""
    registry = pint.get_application_registry()

    for arg in args:
        unit = arg.attrs.get("_unit")
        if not unit:
            log.debug(f"{arg} lacks units; assume dimensionless")
            unit = registry.dimensionless

        arg.attrs["_unit"] = registry.Unit(unit)

    return tuple(arg.attrs["_unit"] for arg in args)


def filter_concat_args(args):
    """Filter out str and Key from *args*.

    A warning is logged for each element removed.
    """
    for arg in args:
        if isinstance(arg, (str, Key)):
            log.warning(f"concat() argument {repr(arg)} missing; will be omitted")
            continue
        yield arg


def parse_units(units_series):
    """Return a :class:`pint.Unit` for a :class:`pd.Series` of strings."""
    unit = pd.unique(units_series)

    if len(unit) > 1:
        raise ValueError(f"mixed units {list(unit)}")

    registry = pint.get_application_registry()

    # Helper method to return an intelligible exception
    def invalid(unit):
        chars = "".join(c for c in "-?$" if c in unit)
        msg = (
            f"unit {repr(unit)} cannot be parsed; contains invalid "
            f"character(s) {repr(chars)}"
        )
        return ValueError(msg)

    # Helper method to add unit definitions
    def define_unit_parts(expr):
        # Split possible compound units
        for part in expr.split("/"):
            try:
                registry.parse_units(part)
            except pint.UndefinedUnitError:
                # Part was unparseable; define it
                definition = f"{part} = [{part}]"
                log.info(f"Add unit definition: {definition}")

                # This line will fail silently for parts like 'G$' containing
                # characters like '$' that are discarded by pint
                registry.define(definition)

    # Parse units
    try:
        unit = clean_units(unit[0])
        unit = registry.parse_units(unit)
    except IndexError:
        # Quantity has no unit
        unit = registry.parse_units("")
    except pint.UndefinedUnitError:
        try:
            # Unit(s) do not exist; define them in the UnitRegistry
            define_unit_parts(unit)

            # Try to parse again
            unit = registry.parse_units(unit)
        except (pint.UndefinedUnitError, pint.RedefinitionError):
            # Handle the silent failure of define(), above; or
            # define_unit_parts didn't work
            raise invalid(unit)
    except AttributeError:
        # Unit contains a character like '-' that throws off pint
        # NB this 'except' clause must be *after* UndefinedUnitError, since
        #    that is a subclass of AttributeError.
        raise invalid(unit)

    return unit


def partial_split(func, kwargs):
    """Forgiving version of :func:`functools.partial`.

    Returns a partial object and leftover kwargs not applicable to `func`.
    """
    # Names of parameters to
    par_names = signature(func).parameters
    func_args, extra = {}, {}
    for name, value in kwargs.items():
        if (
            name in par_names
            and par_names[name].kind == Parameter.POSITIONAL_OR_KEYWORD
        ):
            func_args[name] = value
        else:
            extra[name] = value

    return partial(func, **func_args), extra


def unquote(value):
    """Reverse :func:`dask.core.quote`."""
    if isinstance(value, tuple) and len(value) == 1 and isinstance(value[0], literal):
        return value[0].data
    else:
        return value

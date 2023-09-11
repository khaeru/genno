import logging
from functools import partial
from inspect import Parameter, signature
from typing import Callable, Iterable, Mapping, MutableMapping, Tuple, Type, Union

import numpy as np
import pandas as pd
import pint
from dask.core import literal

from .compat.pint import PintError
from .compat.xarray import is_scalar
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
#: Additional values can be added with :func:`configure`; see :ref:`config-units`.
REPLACE_UNITS = {
    "%": "percent",
}

# For use in type hints
UnitLike = Union[str, pint.Unit, pint.Quantity]


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
    """Return the "_unit" attributes of the `args`."""
    registry = pint.get_application_registry()

    result = []
    for arg in args:
        try:
            unit = arg.attrs.get("_unit")
        except AttributeError:
            if is_scalar(arg):
                result.append(registry.dimensionless)
            else:
                raise  # pragma: no cover
        else:
            if unit is None:
                log.debug(
                    f"{arg.__class__.__name__} '{arg.name or '(no name)'}' {arg.dims!r}"
                    " lacks units; assume dimensionless"
                )
                unit = registry.dimensionless

            # Convert a possible string or other expression to a pint.Unit object
            arg.units = registry.Unit(unit)

            result.append(arg.units)

    return tuple(result)


def filter_concat_args(args):
    """Filter out str and Key from *args*.

    A warning is logged for each element removed.
    """
    for arg in args:
        if isinstance(arg, (str, Key)):
            log.warning(f"concat() argument {repr(arg)} missing; will be omitted")
            continue
        yield arg


def _invalid(unit: str, exc: Exception) -> Exception:
    """Helper method to return an intelligible exception from :func:`parse_units`."""
    chars = "".join(filter("-?$".__contains__, unit))
    msg = f"unit {unit!r} cannot be parsed; contains invalid character(s) {chars!r}"
    # Use the original class of `exc`, mapped in some cases
    cls_map: Mapping[Type[Exception], Type[Exception]] = {TypeError: ValueError}
    return_cls = cls_map.get(type(exc), type(exc))
    return return_cls(msg)


def parse_units(data: Iterable, registry=None) -> pint.Unit:
    """Return a :class:`pint.Unit` for an iterable of strings.

    Valid unit expressions not already present in the `registry` are defined, e.g.:

    .. code-block:: python

       u = parse_units(["foo/bar", "foo/bar"], reg)

    …results in the addition of unit definitions equivalent to:

    .. code-block:: python

       reg.define("foo = [foo]")
       reg.define("bar = [bar]")
       u = reg.foo / reg.bar

    Raises
    ------
    ValueError
        if `data` contains more than 1 unit expression, or the unit expression contains
        characters not parseable by :mod:`pint`, e.g. ``-?$``.
    """
    registry = registry or pint.get_application_registry()

    # Ensure a type that is accepted by pd.unique()
    if isinstance(data, str):
        data = np.array([data])
    elif not isinstance(data, (np.ndarray, pd.Index, pd.Series)):
        data = np.array(data)

    unit = pd.unique(data)

    if len(unit) > 1:
        raise ValueError(f"mixed units {list(unit)}")

    try:
        unit = clean_units(unit[0])
    except IndexError:
        # `units_series` is length 0 → no data → dimensionless
        unit = registry.dimensionless

    # Parse units
    try:
        return registry.Unit(unit)
    except pint.UndefinedUnitError:
        try:
            # Unit(s) do not exist; define them in the UnitRegistry
            # TODO add global configuration to disable this feature.
            # Split possible compound units
            for part in unit.split("/"):
                try:
                    registry.Unit(part)
                except pint.UndefinedUnitError:
                    # Part was unparseable; define it
                    definition = f"{part} = [{part}]"
                    log.info(f"Add unit definition: {definition}")

                    # This line will fail silently for parts like 'G$' containing
                    # characters like '$' that are discarded by pint
                    registry.define(definition)

            # Try to parse again
            return registry.Unit(unit)
        except PintError as e:
            # registry.define() failed somehow
            raise _invalid(unit, e)
    except (AttributeError, TypeError) + PintError as e:  # type: ignore [misc]
        # Unit contains a character like '-' that throws off pint
        # NB this 'except' clause must be *after* UndefinedUnitError, since that is a
        #    subclass of AttributeError.
        raise _invalid(unit, e)


def partial_split(func: Callable, kwargs: Mapping) -> Tuple[Callable, MutableMapping]:
    """Forgiving version of :func:`functools.partial`.

    Returns a :class:`partial` object and leftover kwargs not applicable to `func`.
    """
    # Names of parameters to `func`
    try:
        par_names: Mapping = signature(func).parameters
    except ValueError:
        # signature() raises for operator.itemgetter(…), built-ins, and similar
        if not callable(func):  # pragma: no cover
            raise TypeError(type(func))
        par_names = {}

    func_args, extra = {}, {}
    for name, value in kwargs.items():
        if name in par_names and par_names[name].kind in (
            Parameter.POSITIONAL_OR_KEYWORD,
            Parameter.KEYWORD_ONLY,
        ):
            # A keyword argument of `func`
            func_args[name] = value
        else:
            extra[name] = value

    if func_args:
        return partial(func, **func_args), extra
    else:
        return func, extra  # Nothing to partial; return `func` as-is


def unquote(value):
    """Reverse :func:`dask.core.quote`."""
    if isinstance(value, tuple) and len(value) == 1 and isinstance(value[0], literal):
        return value[0].data
    else:
        return value

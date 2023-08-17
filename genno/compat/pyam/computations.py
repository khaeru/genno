import logging
from functools import partial
from os import PathLike
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Collection, Optional, Union
from warnings import warn

import pyam

import genno.computations
from genno.core.computation import computation
from genno.core.key import Key

from . import util

if TYPE_CHECKING:
    from genno.core.computer import Computer

log = logging.getLogger(__name__)


__all__ = ["as_pyam", "concat", "write_report"]


@computation
def as_pyam(
    self,
    scenario,
    quantity,
    # /,  # Requires Python 3.8; uncomment if/when support for Python 3.7 is dropped
    rename=dict(),
    collapse: Optional[Callable] = None,
    replace=dict(),
    drop: Union[Collection[str], str] = "auto",
    unit=None,
):
    """Return a :class:`pyam.IamDataFrame` containing `quantity`.

    Warnings are logged if the arguments result in additional, unhandled columns in the
    resulting data frame that are not part of the IAMC spec.

    Parameters
    ----------
    scenario :
        Any objects with :attr:`model` and :attr:`scenario` attributes of type
        :class:`str`, e.g. :class:`ixmp.Scenario`.

    Raises
    ------
    ValueError
        If the resulting data frame has duplicate values in the standard IAMC index
        columns. :class:`pyam.IamDataFrame` cannot handle this data.

    See also
    --------
    .Computer.convert_pyam
    """
    # - Convert to pd.DataFrame
    # - Rename one dimension to 'year' or 'time'
    # - Fill variable, unit, model, and scenario columns
    # - Replace values
    # - Apply the collapse callback, if given
    # - Drop any unwanted columns
    # - Clean units
    df = (
        quantity.to_series()
        .rename("value")
        .reset_index()
        .assign(
            variable=quantity.name,
            unit=quantity.attrs.get("_unit", ""),
            # TODO accept these from separate strings
            model=scenario.model,
            scenario=scenario.scenario,
        )
        .rename(columns=rename)
        .pipe(collapse or util.collapse)
        .replace(replace, regex=True)
        .pipe(util.drop, columns=drop)
        .pipe(util.clean_units, unit)
    )

    # Raise exception for non-unique data
    duplicates = df.duplicated(subset=set(df.columns) - {"value"})
    if duplicates.any():
        raise ValueError(
            "Duplicate IAMC indices cannot be converted:\n"
            + str(df[duplicates].drop(columns=["model", "scenario"]))
        )

    return pyam.IamDataFrame(df)


@as_pyam.helper
def add_as_pyam(func, c: "Computer", quantities, tag="iamc", /, **kwargs):
    """Add conversion of one or more `quantities` to IAMC format.

    Parameters
    ----------
    quantities : str or Key or list of (str, Key)
        Keys for quantities to transform.
    tag : str, optional
        Tag to append to new Keys.

    Other parameters
    ----------------
    kwargs :
        Any keyword arguments accepted by :func:`.as_pyam`.

    Returns
    -------
    list of Key
        Each task converts a :class:`.Quantity` into a :class:`pyam.IamDataFrame`.

    See also
    --------
    .as_pyam
    """
    # Handle single vs. iterable of inputs
    multi_arg = not isinstance(quantities, (str, Key))
    if not multi_arg:
        quantities = [quantities]

    if len(kwargs.get("replace", {})) and not isinstance(
        next(iter(kwargs["replace"].values())), dict
    ):
        kwargs["replace"] = dict(variable=kwargs.pop("replace"))
        warn(
            f"replace must be nested dict(), e.g. {repr(kwargs['replace'])}",
            DeprecationWarning,
        )

    # Check keys
    quantities = c.check_keys(*quantities)

    # The callable for the task. If pyam is not available, require_compat() above will
    # fail; so this will never be None
    comp = partial(func, **kwargs)

    keys = []
    for qty in quantities:
        # Key for the input quantity, e.g. foo:x-y-z
        key = Key.from_str_or_key(qty)

        # Key for the task/output, e.g. foo::iamc
        keys.append(Key(key.name, tag=tag))

        # Add the task and store the key
        c.add_single(keys[-1], (comp, "scenario", key))

    return tuple(keys) if multi_arg else keys[0]


def concat(*args, **kwargs):
    """Concatenate *args*, which must all be :class:`pyam.IamDataFrame`."""
    if isinstance(args[0], pyam.IamDataFrame):
        # pyam.concat() takes an iterable of args
        return pyam.concat(args, **kwargs)
    else:
        # genno.computations.concat() takes a variable number of positional arguments
        return genno.computations.concat(*args, **kwargs)


def write_report(obj, path: Union[str, PathLike]) -> None:
    """Write  obj` to the file at `path`.

    If `obj` is a :class:`pyam.IamDataFrame` and `path` ends with ".csv" or ".xlsx",
    use :mod:`pyam` methods to write the file to CSV or Excel format, respectively.
    Otherwise, equivalent to :func:`genno.computations.write_report`.
    """
    if not isinstance(obj, pyam.IamDataFrame):
        return genno.computations.write_report(obj, path)

    path = Path(path)

    if path.suffix == ".csv":
        obj.to_csv(path)
    elif path.suffix == ".xlsx":
        obj.to_excel(path)
    else:
        raise ValueError(
            f"pyam.IamDataFrame can be written to .csv or .xlsx, not {path.suffix}"
        )

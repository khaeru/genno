import logging
from functools import partial
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Callable,
    Collection,
    Iterable,
    Mapping,
    Optional,
    Union,
)
from warnings import warn

import pyam

import genno.operator
from genno.core.key import Key, KeyLike
from genno.core.operator import Operator

from . import util

if TYPE_CHECKING:
    from genno.core.computer import Computer
    from genno.core.quantity import Quantity

log = logging.getLogger(__name__)


__all__ = ["as_pyam"]


@Operator.define()
def as_pyam(
    scenario,
    quantity: "Quantity",
    *,
    rename: Optional[Mapping[str, str]] = None,
    collapse: Optional[Callable] = None,
    replace=dict(),
    drop: Union[Collection[str], str] = "auto",
    unit=None,
):
    """Return a :class:`pyam.IamDataFrame` containing the data from `quantity`.

    Warnings are logged if the arguments result in additional, unhandled columns in the
    resulting data frame that are not part of the IAMC spec.

    The conversion has the following steps:

    1. `quantity` is converted to a temporary :class:`pandas.DataFrame`.
    2. Labels for the following IAMC dimensions are filled:

       - ``model``, ``scenario``: from attributes of the `scenario` argument.
       - ``variable``: from the :attr:`~.Quantity.name` of `quantity`, if any.
       - ``unit``: from the :attr:`~.Quantity.units` of `quantity`, if any.

    3. The actions specified by the optional arguments `rename`, `collapse`, `replace`,
       `drop`, and `unit`, if any, are applied in that order.
    4. The resulting data frame is converted to :class:`pyam.IamDataFrame`.

    Parameters
    ----------
    scenario :
        Any object with :py:`model` and :py:`scenario` attributes of type :class:`str`,
        for instance an :class:`ixmp.Scenario` or
        :class:`~message_ix_models.util.scenarioinfo.ScenarioInfo`.
    rename : dict, optional
        Mapping from dimension names in `quantity` (:class:`str`) to column names
        (:class:`str`); either IAMC dimension names, or others that are consumed by
        `collapse`.
    collapse : callable, optional
        Function that takes a :class:`pandas.DataFrame` and returns the same type.
        This function **may** collapse 2 or more dimensions, for example to construct
        labels for the IAMC ``variable`` dimension, or any other.
    replace : optional
        Values to be replaced and their replaced. Passed directly to
        :meth:`pandas.DataFrame.replace`.
    drop : str or collection of str, optional
        Columns to drop. Passed to :func:`.util.drop`, so if not given, all non-IAMC
        columns are dropped.
    unit : str, optional
        Label for the IAMC ``unit`` dimension. Passed to
        :func:`~.pyam.util.clean_units`.

    Raises
    ------
    ValueError
        If the resulting data frame has duplicate keys in the IAMC dimensions.
        :class:`pyam.IamDataFrame` cannot handle such data.
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
            unit=quantity.units,
            # TODO accept these from separate strings
            model=scenario.model,
            scenario=scenario.scenario,
        )
        .rename(columns=rename or dict())
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
def add_as_pyam(
    func,
    c: "Computer",
    quantities: Union[KeyLike, Iterable[KeyLike]],
    tag="iamc",
    /,
    **kwargs,
):
    """:meth:`.Computer.add` helper for :func:`.as_pyam`.

    Add conversion of one or more `quantities` to the IAMC data structure.

    Parameters
    ----------
    quantities : str or .Key or list of str or .Key
        Keys for quantities to transform.
    tag : str, optional
        Tag to append to new Keys.

    Other parameters
    ----------------
    kwargs :
        Any keyword arguments accepted by :func:`.as_pyam`.

    Returns
    -------
    list of .Key
        Each task converts a :class:`.Quantity` into a :class:`pyam.IamDataFrame`.
    """
    # Handle single vs. iterable of inputs
    if isinstance(quantities, (str, Key)):
        quantities = [quantities]
        multi_arg = False
    else:
        multi_arg = True

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
        key = Key(qty)

        # Key for the task/output, e.g. foo::iamc
        keys.append(Key(key.name, tag=tag))

        # Add the task and store the key
        c.add_single(keys[-1], (comp, "scenario", key))

    return tuple(keys) if multi_arg else keys[0]


@genno.operator.concat.register
def _(*args: pyam.IamDataFrame, **kwargs) -> pyam.IamDataFrame:
    """Concatenate `args`, which must all be :class:`pyam.IamDataFrame`.

    Otherwise, equivalent to :func:`genno.operator.concat`.
    """
    # Use pyam.concat() top-level function
    return pyam.concat(args, **kwargs)


@genno.operator.write_report.register
def _(quantity: pyam.IamDataFrame, path, kwargs=None) -> None:
    """Write  `obj` to the file at `path`.

    If `obj` is a :class:`pyam.IamDataFrame` and `path` ends with ".csv" or ".xlsx",
    use :mod:`pyam` methods to write the file to CSV or Excel format, respectively.
    Otherwise, equivalent to :func:`genno.operator.write_report`.
    """
    path = Path(path)

    if kwargs is not None and len(kwargs):
        raise NotImplementedError(
            "Keyword arguments to write_report(pyam.IamDataFrame, …)"
        )

    if path.suffix == ".csv":
        quantity.to_csv(path)
    elif path.suffix == ".xlsx":
        quantity.to_excel(path)
    else:
        raise ValueError(
            f"pyam.IamDataFrame can be written to .csv or .xlsx, not {path.suffix}"
        )


def __getattr__(name: str):
    if name in ("concat", "write_report"):
        warn(
            f"Importing {name!r} from genno.compat.pyam.operator; import from "
            "genno.operator instead.",
            DeprecationWarning,
            2,
        )

        return getattr(genno.operator, name)
    else:
        raise AttributeError(name)

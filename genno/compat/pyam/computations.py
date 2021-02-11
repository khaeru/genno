import logging
from typing import Callable, Collection, Optional, Union

import pyam

import genno.computations

from . import util

log = logging.getLogger(__name__)


__all__ = ["as_pyam", "concat", "write_report"]


def as_pyam(
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


def concat(*args, **kwargs):
    """Concatenate *args*, which must all be :class:`pyam.IamDataFrame`."""
    if isinstance(args[0], pyam.IamDataFrame):
        # pyam.concat() takes an iterable of args
        return pyam.concat(args, **kwargs)
    else:
        # genno.computations.concat() takes a variable number of positional arguments
        return genno.computations.concat(*args, **kwargs)


def write_report(quantity, path):
    """Write the report identified by *key* to the file at *path*.

    If *quantity* is a :class:`pyam.IamDataFrame` and *path* ends with '.csv' or
    '.xlsx', use :mod:`pyam` methods to write the file to CSV or Excel format,
    respectively. Otherwise, equivalent to :func:`genno.computations.write_report`.
    """
    if not isinstance(quantity, pyam.IamDataFrame):
        return genno.computations.write_report(quantity, path)

    if path.suffix == ".csv":
        quantity.to_csv(path)
    elif path.suffix == ".xlsx":
        quantity.to_excel(path, merge_cells=False)
    else:
        raise ValueError(
            f"pyam.IamDataFrame can be written to .csv or .xlsx, not {path.suffix}"
        )

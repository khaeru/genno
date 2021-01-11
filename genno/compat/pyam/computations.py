import logging

import pint
import pyam

import genno.computations

log = logging.getLogger(__name__)


def as_pyam(
    scenario,
    quantity,
    replace_vars=None,
    year_time_dim=None,
    drop=[],
    collapse=None,
    unit=None,
):
    """Return a :class:`pyam.IamDataFrame` containing *quantity*.

    Warnings are logged if the arguments result in additional, unhandled columns in the
    resulting data frame that are not part of the IAMC spec.

    Raises
    ------
    ValueError
        If the resulting data frame has duplicate values in the standard IAMC index
        columns. :class:`pyam.IamDataFrame` cannot handle this data.

    See also
    --------
    .Computer.convert_pyam
    """
    rename_cols = {
        # Renamed automatically
        "n": "region",
        "nl": "region",
        # Column to set as year or time dimension
        year_time_dim: "year" if year_time_dim.startswith("y") else "time",
    }

    # - Convert to pd.DataFrame
    # - Rename one dimension to 'year' or 'time'
    # - Fill variable, unit, model, and scenario columns
    # - Apply the collapse callback, if given
    # - Replace values in the variable column
    # - Drop any unwanted columns
    df = (
        quantity.to_series()
        .rename("value")
        .reset_index()
        .rename(columns=rename_cols)
        .assign(
            variable=quantity.name,
            unit=quantity.attrs.get("_unit", ""),
            model=scenario.model,
            scenario=scenario.scenario,
        )
        .pipe(collapse or (lambda df: df))
        .replace(dict(variable=replace_vars or dict()))
        .drop(drop, axis=1)
    )

    # Raise exception for non-unique data
    duplicates = df.duplicated(subset=set(df.columns) - {"value"})
    if duplicates.any():
        raise ValueError(
            "Duplicate IAMC indices cannot be converted:\n" + str(df[duplicates])
        )

    # Convert units
    if len(df) and unit:
        from_unit = df["unit"].unique()
        if len(from_unit) > 1:
            raise ValueError(f"cannot convert non-unique units {repr(from_unit)}")
        q = pint.Quantity(df["value"].values, from_unit[0]).to(unit)
        df["value"] = q.magnitude
        df["unit"] = unit

    # Ensure units are a string, for pyam
    if len(df) and not isinstance(df.loc[0, "unit"], str):
        # Convert pint.Unit to string
        df["unit"] = f"{df.loc[0, 'unit']:~}"

    # Warn about extra columns
    extra = sorted(set(df.columns) - set(pyam.IAMC_IDX + ["year", "time", "value"]))
    if extra:
        log.warning(
            f"Extra columns {repr(extra)} when converting "
            f"{repr(quantity.name)} to IAMC format"
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

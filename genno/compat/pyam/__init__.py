from logging import getLogger

import pint
from pyam import IAMC_IDX, IamDataFrame

log = getLogger(__name__)


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
    extra = sorted(set(df.columns) - set(IAMC_IDX + ["year", "time", "value"]))
    if extra:
        log.warning(
            f"Extra columns {repr(extra)} when converting "
            f"{repr(quantity.name)} to IAMC format"
        )

    return IamDataFrame(df)


def collapse_message_cols(df, var, kind=None):
    """:meth:`as_pyam` `collapse=...` callback for MESSAGE quantities.

    Parameters
    ----------
    var : str
        Name for 'variable' column.
    kind : None or 'ene' or 'emi', optional
        Determines which other columns are combined into the 'region' and
        'variable' columns:

        - 'ene': 'variable' is
          ``'<var>|<level>|<commodity>|<technology>|<mode>'`` and 'region' is
          ``'<region>|<node_dest>'`` (if `var='out'`) or
          ``'<region>|<node_origin>'`` (if `'var='in'`).
        - 'emi': 'variable' is ``'<var>|<emission>|<technology>|<mode>'``.
        - Otherwise: 'variable' is ``'<var>|<technology>'``.

        The referenced columns are also dropped, so it is not necessary to
        provide the `drop` argument of :meth:`as_pyam`.
    """
    if kind == "ene":
        # Region column
        rcol = "nd" if var == "out" else "no"
        df["region"] = df["region"].str.cat(df[rcol], sep="|")
        df.drop(rcol, axis=1, inplace=True)

        var_cols = ["l", "c", "t", "m"]
    elif kind == "emi":
        var_cols = ["e", "t", "m"]
    else:
        var_cols = ["t"]

    # Assemble variable column
    df["variable"] = var
    df["variable"] = df["variable"].str.cat([df[c] for c in var_cols], sep="|")

    # Drop same columns
    return df.drop(var_cols, axis=1)

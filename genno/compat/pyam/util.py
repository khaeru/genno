import logging
from typing import Collection, Mapping, Sequence, Union

import pandas as pd
import pint
import pyam

log = logging.getLogger(__name__)


IAMC_IDX = frozenset(pyam.IAMC_IDX + ["year", "time"])


def clean_units(df: pd.DataFrame, unit=None) -> pd.DataFrame:
    """Convert magnitudes and units of `df` to `unit` in :class:`str`.

    Raises
    ------
    ValueError
        if there is more than one unit.
    """
    # Convert units
    if len(df) == 0:
        return df

    if unit:
        from_unit = df["unit"].unique()
        if len(from_unit) > 1:
            raise ValueError(f"cannot convert non-unique units {list(from_unit)}")
        q = pint.Quantity(df["value"].values, from_unit[0]).to(unit)
        df["value"] = q.magnitude
        df["unit"] = unit

    # pyam requires units are str, not pint.Unit
    if not isinstance(df.loc[0, "unit"], str):
        df["unit"] = f"{df.loc[0, 'unit']:~}"

    return df


def collapse(
    df: pd.DataFrame, columns: Mapping[str, Sequence[str]] = dict(), sep="|"
) -> pd.DataFrame:
    """Collapse `columns` into the IAMC columns of `df`."""
    to_drop = set()

    for target_col, values in columns.items():
        if target_col not in IAMC_IDX:
            raise ValueError(f"non-IAMC column {repr(target_col)}")

        entries = []
        for v in values:
            if v in df:
                entries.append(df[v])
                to_drop.add(v)
            else:
                entries.append(pd.Series(str(v), index=df.index))

        if target_col not in df or df[target_col].isna().all():
            # df doesn't contain the column, or all entries are None, e.g. if
            # quantity.name was not set. Initialize with first entry.
            df[target_col] = entries.pop(0)

        df[target_col] = df[target_col].str.cat(entries, sep=sep)

    return df.drop(to_drop, axis=1)


def _extra(obj):
    """Extra columns in `obj`."""
    return sorted(set(obj.columns) - IAMC_IDX - {"value"})


def drop(df: pd.DataFrame, columns: Union[Collection[str], str]) -> pd.DataFrame:
    """Drop `columns` if given, or all non-IAMC columns."""

    if isinstance(columns, str):
        if columns != "auto":
            raise ValueError(columns)
        # Drop all non-IAMC columns
        return df.drop(_extra(df), axis=1)
    else:
        result = df.drop(columns, axis=1)
        extra = _extra(result)
        if extra:
            log.info(f"Extra columns {repr(extra)} when converting to IAMC format")
        return result

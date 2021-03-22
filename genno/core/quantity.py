from typing import Tuple

import pandas as pd
import pint

#: Name of the class used to implement :class:`.Quantity`.
CLASS = "AttrSeries"
# CLASS = "SparseDataArray"


class Quantity:
    # To silence a warning in xarray
    __slots__: Tuple[str, ...] = tuple()

    def __new__(cls, *args, **kwargs):
        # Use _get_class() to retrieve either AttrSeries or SparseDataArray
        return object.__new__(Quantity._get_class(cls))

    def to_series(self) -> pd.Series:
        """Like :meth:`xarray.DataArray.to_series`."""
        # Provided only for type-checking in other packages. AttrSeries implements;
        # SparseDataArray uses the xr.DataArray method.

    @classmethod
    def from_series(cls, series, sparse=True):
        """Convert `series` to the Quantity class given by :data:`.CLASS`."""
        # NB signature is the same as xr.DataArray.from_series(); except sparse=True
        assert sparse
        return cls._get_class().from_series(series, sparse)

    # Internal methods

    @staticmethod
    def _get_class(cls=None):
        """Get :class:`.AttrSeries` or :class:`.SparseDataArray`, per :data:`.CLASS`."""
        if cls in (Quantity, None):
            if CLASS == "AttrSeries":
                from .attrseries import AttrSeries as cls
            elif CLASS == "SparseDataArray":
                from .sparsedataarray import SparseDataArray as cls
            else:  # pragma: no cover
                raise ValueError(CLASS)

        return cls

    @staticmethod
    def _single_column_df(data, name):
        """Handle `data` and `name` arguments to Quantity constructors."""
        if isinstance(data, pd.DataFrame):
            if len(data.columns) != 1:
                raise TypeError(
                    f"Cannot instantiate Quantity from {len(data.columns)}-D data frame"
                )

            # Unpack a single column; use its name if not overridden by `name`
            return data.iloc[:, 0], (name or data.columns[0])
        # NB would prefer to do this, but pandas has several bugs for MultiIndex with
        #    only 1 level
        # elif (
        #     isinstance(data, pd.Series) and not isinstance(data.index, pd.MultiIndex)
        # ):
        #     return data.set_axis(pd.MultiIndex.from_product([data.index])), name
        else:
            return data, name

    @staticmethod
    def _collect_attrs(data, attrs_arg, kwargs):
        """Handle `attrs` and 'units' `kwargs` to Quantity constructors."""
        # Use attrs, if any, from an existing object, if any
        new_attrs = getattr(data, "attrs", dict()).copy()

        # Overwrite with values from an explicit attrs argument
        new_attrs.update(attrs_arg or dict())

        # Store the "units" keyword argument as an attr
        units = kwargs.pop("units", None)
        if units:
            new_attrs["_unit"] = pint.Unit(units)

        return new_attrs


def assert_quantity(*args):
    """Assert that each of `args` is a Quantity object.

    Raises
    ------
    TypeError
        with a indicative message.
    """
    for i, arg in enumerate(args):
        if not isinstance(arg, Quantity):
            raise TypeError(
                f"arg #{i+1} ({repr(arg)}) is not Quantity; likely an incorrect key"
            )

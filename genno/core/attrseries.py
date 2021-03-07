import logging
from typing import Any, Hashable, Mapping

import pandas as pd
import pandas.core.indexes.base as ibase
import xarray as xr

from genno.core.quantity import Quantity

log = logging.getLogger(__name__)


class AttrSeries(pd.Series, Quantity):
    """:class:`pandas.Series` subclass imitating :class:`xarray.DataArray`.

    The AttrSeries class provides similar methods and behaviour to
    :class:`xarray.DataArray`, so that :mod:`genno.computations` methods can use xarray-
    like syntax.

    Parameters
    ----------
    units : str or pint.Unit, optional
        Set the units attribute. The value is converted to :class:`pint.Unit` and added
        to `attrs`.
    attrs : :class:`~collections.abc.Mapping`, optional
        Set the :attr:`~pandas.Series.attrs` of the AttrSeries. This attribute was added
        in `pandas 1.0 <https://pandas.pydata.org/docs/whatsnew/v1.0.0.html>`_, but is
        not currently supported by the Series constructor.
    """

    # See https://pandas.pydata.org/docs/development/extending.html
    @property
    def _constructor(self):
        return AttrSeries

    def __init__(self, data=None, *args, name=None, attrs=None, **kwargs):
        attrs = Quantity._collect_attrs(data, attrs, kwargs)

        if isinstance(data, (pd.Series, xr.DataArray)):
            # Extract name from existing object or use the argument
            name = ibase.maybe_extract_name(name, data, type(self))

            try:
                # Pre-convert to pd.Series from xr.DataArray to preserve names and
                # labels. For AttrSeries, this is a no-op (see below).
                data = data.to_series()
            except AttributeError:
                # pd.Series
                pass
            except ValueError:
                # xr.DataArray
                if data.shape == tuple():
                    # data is a scalar/0-dimensional xr.DataArray. Pass the 1 value
                    data = data.data
                else:  # pragma: no cover
                    raise
            else:
                attrs.update()

        data, name = Quantity._single_column_df(data, name)

        # Don't pass attrs to pd.Series constructor; it currently does not accept them
        pd.Series.__init__(self, data, *args, name=name, **kwargs)

        # Update the attrs after initialization
        self.attrs.update(attrs)

    @classmethod
    def from_series(cls, series, sparse=None):
        """Like :meth:`xarray.DataArray.from_series`."""
        return AttrSeries(series)

    def assign_coords(self, **kwargs):
        """Like :meth:`xarray.DataArray.assign_coords`."""
        return pd.concat([self], keys=kwargs.values(), names=kwargs.keys())

    def bfill(self, dim: Hashable, limit: int = None):
        """Like :meth:`xarray.DataArray.bfill`."""
        return self.__class__(
            self.unstack(dim)
            .fillna(method="bfill", axis=1, limit=limit)
            .stack()
            .reorder_levels(self.dims),
            attrs=self.attrs,
        )

    @property
    def coords(self):
        """Like :attr:`xarray.DataArray.coords`. Read-only."""
        result = dict()
        for name, levels in zip(self.index.names, self.index.levels):
            result[name] = xr.Dataset(None, coords={name: levels})[name]
        return result

    def cumprod(self, dim=None, axis=None, skipna=None, **kwargs):
        """Like :attr:`xarray.DataArray.cumprod`."""
        if axis:
            log.info(f"{self.__class__.__name__}.cumprod(…, axis=…) is ignored")

        return self.__class__(
            self.unstack(dim)
            .cumprod(axis=1, skipna=skipna, **kwargs)
            .stack()
            .reorder_levels(self.dims),
            attrs=self.attrs,
        )

    @property
    def dims(self):
        """Like :attr:`xarray.DataArray.dims`."""
        return tuple(self.index.names)

    def drop(self, label):
        """Like :meth:`xarray.DataArray.drop`."""
        return self.droplevel(label)

    def ffill(self, dim: Hashable, limit: int = None):
        """Like :meth:`xarray.DataArray.ffill`."""
        return self.__class__(
            self.unstack(dim)
            .fillna(method="ffill", axis=1, limit=limit)
            .stack()
            .reorder_levels(self.dims),
            attrs=self.attrs,
        )

    def item(self, *args):
        """Like :meth:`xarray.DataArray.item`."""
        if len(args) and args != (None,):
            raise NotImplementedError
        elif self.size != 1:
            raise ValueError
        return self.iloc[0]

    def rename(self, new_name_or_name_dict):
        """Like :meth:`xarray.DataArray.rename`."""
        if isinstance(new_name_or_name_dict, dict):
            return self.rename_axis(index=new_name_or_name_dict)
        else:
            return super().rename(new_name_or_name_dict)

    def sel(self, indexers=None, drop=False, **indexers_kwargs):
        """Like :meth:`xarray.DataArray.sel`."""
        indexers = xr.core.utils.either_dict_or_kwargs(
            indexers, indexers_kwargs, "indexers"
        )

        if len(indexers) == 1:
            level, key = list(indexers.items())[0]
            if isinstance(key, str) and not drop:
                if isinstance(self.index, pd.MultiIndex):
                    # When using .loc[] to select 1 label on 1 level, pandas drops the
                    # level. Use .xs() to avoid this behaviour unless drop=True
                    return AttrSeries(self.xs(key, level=level, drop_level=False))
                else:
                    # No MultiIndex; use .loc with a slice to avoid returning scalar
                    return self.loc[slice(key, key)]

        # Iterate over dimensions
        idx = []
        for dim in self.dims:
            # Get an indexer for this dimension
            i = indexers.get(dim, slice(None))

            # Maybe unpack an xarray DataArray indexers, for pandas
            idx.append(i.data if isinstance(i, xr.DataArray) else i)

        # Select and return
        return AttrSeries(self.loc[tuple(idx)])

    def shift(
        self,
        shifts: Mapping[Hashable, int] = None,
        fill_value: Any = None,
        **shifts_kwargs: int,
    ):
        """Like :meth:`xarray.DataArray.shift`."""
        shifts = xr.core.utils.either_dict_or_kwargs(shifts, shifts_kwargs, "shift")
        if len(shifts) > 1:
            raise NotImplementedError(
                f"{self.__class__.__name__}.shift() with > 1 dimension"
            )

        dim, periods = next(iter(shifts.items()))
        return self.__class__(
            self.unstack(dim)
            .shift(periods=periods, axis=1, fill_value=fill_value)
            .stack()
            .reorder_levels(self.dims),
            attrs=self.attrs,
        )

    def sum(self, *args, **kwargs):
        """Like :meth:`xarray.DataArray.sum`."""
        obj = super()
        attrs = None

        try:
            dim = kwargs.pop("dim")
        except KeyError:
            dim = list(args)
            args = tuple()

        if len(dim) in (0, len(self.index.names)):
            bad_dims = set(dim) - set(self.index.names)
            if bad_dims:
                raise ValueError(
                    f"{bad_dims} not found in array dimensions {self.index.names}"
                )
            # Simple sum
            kwargs = {}
        else:
            # Pivot and sum across columns
            obj = self.unstack(dim)
            kwargs["axis"] = 1
            # Result will be DataFrame; re-attach attrs when converted to AttrSeries
            attrs = self.attrs

        return AttrSeries(obj.sum(*args, **kwargs), attrs=attrs)

    def squeeze(self, dim=None, *args, **kwargs):
        """Like :meth:`xarray.DataArray.squeeze`."""
        assert kwargs.pop("drop", True)

        try:
            idx = self.index.remove_unused_levels()
        except AttributeError:
            return self

        to_drop = []
        for i, name in enumerate(idx.names):
            if dim and name != dim:
                continue
            elif len(idx.levels[i]) > 1:
                if dim is None:
                    continue
                else:
                    raise ValueError(
                        "cannot select a dimension to squeeze out which has length "
                        "greater than one"
                    )

            to_drop.append(name)

        if dim and not to_drop:
            # Specified dimension does not exist
            raise KeyError(dim)

        return self.droplevel(to_drop)

    def transpose(self, *dims):
        """Like :meth:`xarray.DataArray.transpose`."""
        return self.reorder_levels(dims)

    def to_dataframe(self):
        """Like :meth:`xarray.DataArray.to_dataframe`."""
        return self.to_frame()

    def to_series(self):
        """Like :meth:`xarray.DataArray.to_series`."""
        return self

    # Internal methods

    def align_levels(self, other):
        """Work around https://github.com/pandas-dev/pandas/issues/25760.

        Return a copy of `self` with common levels in the same order as `other`.
        """
        # Lists of common dimensions, and dimensions on `other` missing from `self`.
        common, missing = [], []
        for (i, n) in enumerate(other.index.names):
            if n in self.index.names:
                common.append(n)
            else:
                missing.append((i, n))

        result = self
        if len(common) == 0:
            # Broadcast over missing dimensions
            # TODO make this more efficient, e.g. using itertools.product()
            for i, dim in missing:
                result = pd.concat(
                    {v: result for v in other.index.get_level_values(i)}, names=[dim]
                )

            if len(self) == len(self.index.names) == 1:
                # concat() of scalars (= length-1 pd.Series) results in an innermost
                # index level filled with int(0); discard this
                result = result.droplevel(-1)

            # Reordering starts with the dimensions of `other`
            order = list(other.index.names)
        else:
            # Some common dimensions exist; no need to broadcast, only reorder
            order = common

        # Append the dimensions of `self`
        order.extend(
            filter(
                lambda n: n is not None and n not in other.index.names, self.index.names
            )
        )

        # Reorder, if that would do anything
        return result.reorder_levels(order) if len(order) > 1 else result

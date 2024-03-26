import logging
from typing import Any, Dict, Hashable, Mapping, Optional, Sequence, Tuple, Union
from warnings import filterwarnings

import numpy as np
import pandas as pd

try:
    import sparse

    HAS_SPARSE = True
except ImportError:  # pragma: no cover
    HAS_SPARSE = False

import xarray as xr

from genno.compat.xarray import dtypes, either_dict_or_kwargs

from .base import BaseQuantity, collect_attrs, rank, single_column_df

log = logging.getLogger(__name__)

# Occurs below in SparseDataArray.squeeze()
filterwarnings(
    "ignore",
    "Conversion of an array with ndim > 0 to a scalar is deprecated, and will error in "
    "future.",
    DeprecationWarning,
    "sparse",
)


@xr.register_dataarray_accessor("_sda")
class SparseAccessor:
    """:mod:`xarray` accessor to help :class:`SparseDataArray`.

    See the xarray accessor documentation, e.g.
    :func:`~xarray.register_dataarray_accessor`.
    """

    def __init__(self, obj):
        self.da = obj

    def convert(self):
        """Return a :class:`SparseDataArray` instance."""
        if not self.da._sda.COO_data:
            # Dense (numpy.ndarray) data; convert to sparse
            data = sparse.COO.from_numpy(self.da.data, fill_value=np.nan)
        elif not np.isnan(self.da.data.fill_value):
            # sparse.COO with non-NaN fill value; copy and change
            data = self.da.data.copy(deep=False)
            data.fill_value = data.dtype.type(np.nan)
        else:
            # No change
            data = self.da.data

        if isinstance(self.da, SparseDataArray):
            # Replace the variable, returning a copy
            variable = self.da.variable._replace(data=data)
            return self.da._replace(variable=variable)
        else:
            # Construct
            return SparseDataArray(
                data=data,
                coords=self.da.coords,
                dims=self.da.dims,
                name=self.da.name,
                attrs=self.da.attrs,
            )

    @property
    def COO_data(self):
        """:obj:`True` if the DataArray has :class:`sparse.COO` data."""
        return isinstance(self.da.data, sparse.COO)

    @property
    def dense(self):
        """Return a copy with dense (:class:`numpy.ndarray`) data."""
        try:
            # Use existing method xr.Variable._to_dense()
            return self.da._replace(variable=self.da.variable._to_dense())
        except TypeError:
            # self.da.variable was already dense
            return self.da

    @property
    def dense_super(self):
        """Return a proxy to a :class:`numpy.ndarray`-backed :class:`xarray.DataArray`."""
        return super(SparseDataArray, self.dense)


class OverrideItem:
    """Override :meth:`xarray.DataArray.item`.

    The :meth:`item` method is set dynamically by
    :class:`xarray.ops.IncludeNumpySameMethods`, a parent of
    :class:`xarray.arithmetic.DataArrayArithmetic` and thus of DataArray.
    That has the effect of overriding an ordinary :meth:`item` method defined on
    :class:`SparseDataArray`.

    This class, placed higher in the MRO for SparseDataArray, cancels out that effect.
    """

    __slots__ = ()

    def __init_subclass__(cls, **kwargs):
        setattr(cls, "item", cls._item)


class SparseDataArray(BaseQuantity, OverrideItem, xr.DataArray):
    """:class:`~xarray.DataArray` with sparse data.

    SparseDataArray uses :class:`sparse.COO` for storage with :data:`numpy.nan`
    as its :attr:`sparse.SparseArray.fill_value`. Some methods of
    :class:`~xarray.DataArray` are overridden to ensure data is in sparse, or dense,
    format as necessary, to provide expected functionality not currently supported by
    :mod:`sparse`, and to avoid exhausting memory for some operations that require dense
    data.
    """

    __slots__: Tuple[str, ...] = tuple()

    def __init__(
        self,
        data: Any = dtypes.NA,
        coords: Union[Sequence[Tuple], Mapping[Hashable, Any], None] = None,
        dims: Union[str, Sequence[Hashable], None] = None,
        name: Hashable = None,
        attrs: Optional[Mapping] = None,
        # internal parameters
        indexes: Optional[Dict[Hashable, pd.Index]] = None,
        fastpath: bool = False,
        **kwargs,
    ):
        if fastpath:
            return xr.DataArray.__init__(
                self, data, coords, dims, name, attrs, indexes, fastpath
            )

        attrs = collect_attrs(data, attrs, kwargs)

        assert 0 == len(
            kwargs
        ), f"Unrecognized kwargs {kwargs.keys()} to SparseDataArray()"

        if isinstance(data, int):
            data = float(data)

        data, name = single_column_df(data, name)

        if isinstance(data, pd.Series):
            # Possibly converted from pd.DataFrame, above
            if data.dtype == int:
                # Ensure float data
                data = data.astype(float)
            data = xr.DataArray.from_series(data, sparse=True)

        if isinstance(data, xr.DataArray):
            # Possibly converted from pd.Series, above
            coords = data._coords
            name = name or data.name
            data = data.variable

        # Invoke the xr.DataArray constructor
        xr.DataArray.__init__(self, data, coords, dims, name, attrs)

        if not isinstance(self.variable.data, sparse.COO):
            dtype = self.variable.data.dtype

            if issubclass(dtype.type, np.integer):
                log.warning(f"Force dtype {self.variable.data.dtype} → float")
                dtype = float

            # Dense (numpy.ndarray) data; convert to sparse
            data = sparse.COO.from_numpy(
                self.variable.data.astype(dtype), fill_value=np.nan
            )
        elif not np.isnan(self.variable.data.fill_value):
            # sparse.COO with non-NaN fill value; copy and change
            data = self.variable.data.copy(deep=False)
            data.fill_value = data.dtype.type(np.nan)
        else:
            # No change
            return

        # Replace the variable
        self._variable = self._variable._replace(data=data)

    @classmethod
    def from_series(cls, obj, sparse=True):
        """Convert a pandas.Series into a SparseDataArray."""
        # Call the parent method always with sparse=True, then re-wrap
        return xr.DataArray.from_series(obj, sparse=True)._sda.convert()

    @staticmethod
    def _perform_binary_op(
        op, left: "SparseDataArray", right: "SparseDataArray", factor: float
    ) -> "SparseDataArray":
        # xr.DataArray-specific: outer join
        if rank(op) == 1:
            left, right = xr.align(left, right, join="outer", fill_value=0.0)

        # super() `left` if this hasn't already happened
        left_ = left if isinstance(left, super) else super(xr.DataArray, left)
        # Invoke an xr.DataArray method like .__mul__()
        return getattr(left_, f"__{op.__name__}__")(right)

    def __len__(self) -> int:
        v = self.variable
        return 0 if getattr(v.data, "nnz", 1) == 0 else len(v)

    @property
    def size(self) -> int:
        return 0 if getattr(self.variable.data, "nnz", 1) == 0 else self.variable.size

    def clip(self, min=None, max=None, *, keep_attrs=None):
        """Override :meth:`~xarray.DataArray.clip` to return SparseDataArray."""
        return super().clip(min, max, keep_attrs=keep_attrs)._sda.convert()

    def ffill(self, dim: Hashable, limit: Optional[int] = None):
        """Override :meth:`~xarray.DataArray.ffill` to auto-densify."""
        return self._sda.dense_super.ffill(dim, limit)._sda.convert()

    def interp(
        self,
        coords=None,
        method="linear",
        assume_sorted=False,
        kwargs=None,
        **coords_kwargs: Any,
    ):
        """Override :meth:`~xarray.DataArray.interp` to auto-densify."""
        return self._sda.dense_super.interp(
            coords, method, assume_sorted, kwargs, **coords_kwargs
        )._sda.convert()

    def _item(self, *args):
        """Like :meth:`~xarray.DataArray.item`."""
        # See OverrideItem
        d = self.data
        if args:
            raise NotImplementedError("item() with args")
        elif d.size > 1:
            raise ValueError("can only convert an array of size 1 to a Python scalar")
        elif isinstance(d, sparse.COO):
            # sparse.COO.item() does not exist
            return d.fill_value if d.nnz == 0 else d.data.tolist()[0]
        else:  # numpy.ndarray or something else
            return d.item()

    def sel(
        self,
        indexers: Optional[Mapping[Any, Any]] = None,
        method: Optional[str] = None,
        tolerance=None,
        drop: bool = False,
        **indexers_kwargs: Any,
    ) -> "SparseDataArray":
        """Return a new array by selecting labels along the specified dim(s).

        Overrides :meth:`~xarray.DataArray.sel` to handle >1-D indexers with sparse
        data.
        """
        indexers = either_dict_or_kwargs(indexers, indexers_kwargs, "sel")
        if isinstance(indexers, dict) and len(indexers) > 1:
            result = self
            for k, v in indexers.items():
                result = result.sel(
                    {k: v}, method=method, tolerance=tolerance, drop=drop
                )
        else:
            result = (
                super()
                .sel(indexers=indexers, method=method, tolerance=tolerance, drop=drop)
                ._sda.convert()
            )
        return self._keep(result, name=True, attrs=True)

    def squeeze(self, dim=None, drop=False, axis=None):
        return self._sda.dense_super.squeeze(
            dim=dim, drop=drop, axis=axis
        )._sda.convert()

    def to_dataframe(
        self,
        name: Optional[Hashable] = None,
        dim_order: Optional[Sequence[Hashable]] = None,
    ) -> pd.DataFrame:
        """Convert this array and its coords into a :class:`pandas.DataFrame`.

        Overrides :meth:`~xarray.DataArray.to_dataframe`.
        """
        if dim_order is not None:
            raise NotImplementedError("dim_order arg to to_dataframe()")
        return self.to_series().to_frame(name or self.name or "value")

    def to_series(self) -> pd.Series:
        """Convert this array into a :class:`~pandas.Series`.

        Overrides :meth:`~xarray.DataArray.to_series` to create the series without
        first converting to a potentially very large :class:`numpy.ndarray`.
        """
        # Use SparseArray.coords and .data (each already 1-D) to construct the pd.Series

        # Construct a pd.MultiIndex without using .from_product
        if self.dims:
            index = pd.MultiIndex.from_arrays(
                self.data.coords, names=self.dims
            ).set_levels([self.coords[d].values for d in self.dims])
        else:
            index = pd.MultiIndex.from_arrays([[0]], names=[None])

        return pd.Series(self.data.data, index=index, name=self.name)

    def where(self, cond: Any, other: Any = dtypes.NA, drop: bool = False):
        """Override :meth:`~xarray.DataArray.where` to auto-densify."""
        return self._sda.dense_super.where(cond, other, drop)._sda.convert()

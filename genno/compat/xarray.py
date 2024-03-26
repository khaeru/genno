"""Compatibility with :mod:`xarray`."""

from abc import abstractmethod
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Hashable,
    Iterable,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    TypeVar,
    Union,
)

import numpy as np
import pandas as pd
import xarray
from xarray.core import dtypes
from xarray.core.coordinates import Coordinates
from xarray.core.indexes import Indexes
from xarray.core.utils import either_dict_or_kwargs, is_scalar

if TYPE_CHECKING:
    import xarray.core.types
    from xarray.core.types import Dims

T = TypeVar("T", covariant=True)

__all__ = [
    "Coordinates",
    "DataArrayLike",
    "Indexes",
    "dtypes",
    "either_dict_or_kwargs",
    "is_scalar",
]


class DataArrayLike(Protocol):
    """Protocol for a :class:`.xarray.DataArray` -like API.

    This class is used to set signatures and types for methods and attributes on
    :class:`.AttrSeries` class, which then supplies implementations of each method.
    Objects typed :class:`.AnyQuantity` see either the signatures of this protocol, or
    identical signatures for the same methods on :class:`~xarray.DataArray` via
    :class:`.SparseDataArray`.
    """

    # Type hints for mypy in downstream applications
    @abstractmethod
    def __len__(self) -> int: ...

    def __mod__(self, other): ...
    def __mul__(self, other): ...
    def __neg__(self): ...
    def __pow__(self, other): ...
    def __radd__(self, other): ...
    def __rmul__(self, other): ...
    def __rsub__(self, other): ...
    def __rtruediv__(self, other): ...
    def __truediv__(self, other): ...

    @property
    @abstractmethod
    def data(self) -> Any: ...

    @property
    @abstractmethod
    def coords(self) -> xarray.core.coordinates.DataArrayCoordinates: ...

    @property
    @abstractmethod
    def dims(self) -> Tuple[Hashable, ...]: ...

    @property
    @abstractmethod
    def shape(self) -> Tuple[int, ...]: ...

    @property
    @abstractmethod
    def size(self) -> int: ...

    def assign_coords(
        self,
        coords: Optional[Mapping[Any, Any]] = None,
        **coords_kwargs: Any,
    ): ...

    @abstractmethod
    def astype(
        self,
        dtype,
        *,
        order=None,
        casting=None,
        subok=None,
        copy=None,
        keep_attrs=True,
    ): ...

    @abstractmethod
    def bfill(
        self,
        dim: Hashable,
        limit: Optional[int] = None,
    ): ...

    @abstractmethod
    def clip(
        self,
        min: Optional["xarray.core.types.ScalarOrArray"] = None,
        max: Optional["xarray.core.types.ScalarOrArray"] = None,
        *,
        keep_attrs: Optional[bool] = None,
    ): ...

    @abstractmethod
    def copy(
        self,
        deep: bool = True,
        data: Any = None,
    ): ...

    @abstractmethod
    def cumprod(
        self,
        dim: "Dims" = None,
        *,
        skipna: Optional[bool] = None,
        keep_attrs: Optional[bool] = None,
        **kwargs: Any,
    ): ...

    @abstractmethod
    def drop_vars(
        self,
        names: Union[
            str, Iterable[Hashable], Callable[[Any], Union[str, Iterable[Hashable]]]
        ],
        *,
        errors="raise",
    ): ...

    @abstractmethod
    def expand_dims(
        self,
        dim=None,
        axis=None,
        **dim_kwargs: Any,
    ): ...

    @abstractmethod
    def ffill(
        self,
        dim: Hashable,
        limit: Optional[int] = None,
    ): ...

    @abstractmethod
    def groupby(
        self,
        group,
        squeeze: bool = True,
        restore_coord_dims: bool = False,
    ): ...

    @abstractmethod
    def interp(
        self,
        coords: Optional[Mapping[Any, Any]] = None,
        method: "xarray.core.types.InterpOptions" = "linear",
        assume_sorted: bool = False,
        kwargs: Optional[Mapping[str, Any]] = None,
        **coords_kwargs: Any,
    ): ...

    @abstractmethod
    def item(self, *args): ...

    @abstractmethod
    def max(
        self,
        dim: "Dims" = None,
        *,
        skipna: Optional[bool] = None,
        keep_attrs: Optional[bool] = None,
        **kwargs: Any,
    ): ...

    @abstractmethod
    def min(
        self,
        dim: "Dims" = None,
        *,
        skipna: Optional[bool] = None,
        keep_attrs: Optional[bool] = None,
        **kwargs: Any,
    ): ...

    @abstractmethod
    def pipe(
        self,
        func: Union[Callable[..., T], Tuple[Callable[..., T], str]],
        *args: Any,
        **kwargs: Any,
    ): ...

    @abstractmethod
    def rename(
        self,
        new_name_or_name_dict: Union[Hashable, Mapping[Any, Hashable]] = None,
        **names: Hashable,
    ): ...

    @abstractmethod
    def round(self, *args, **kwargs): ...

    @abstractmethod
    def sel(
        self,
        indexers: Optional[Mapping[Any, Any]] = None,
        method: Optional[str] = None,
        tolerance=None,
        drop: bool = False,
        **indexers_kwargs: Any,
    ): ...

    @abstractmethod
    def shift(
        self,
        shifts: Optional[Mapping[Any, int]] = None,
        fill_value: Any = None,
        **shifts_kwargs: int,
    ): ...

    def squeeze(
        self,
        dim: Union[Hashable, Iterable[Hashable], None] = None,
        drop: bool = False,
        axis: Union[int, Iterable[int], None] = None,
    ): ...

    @abstractmethod
    def sum(
        self,
        dim: "Dims" = None,
        # Signature from xarray.DataArray
        *,
        skipna: Optional[bool] = None,
        min_count: Optional[int] = None,
        keep_attrs: Optional[bool] = None,
        **kwargs: Any,
    ): ...

    @abstractmethod
    def to_dataframe(
        self,
        name: Optional[Hashable] = None,
        dim_order: Optional[Sequence[Hashable]] = None,
    ) -> pd.DataFrame: ...

    @abstractmethod
    def to_numpy(self) -> np.ndarray: ...

    @abstractmethod
    def where(self, cond: Any, other: Any = dtypes.NA, drop: bool = False): ...

    # Provided only for type-checking in other packages. AttrSeries implements;
    # SparseDataArray uses the xr.DataArray method.
    @abstractmethod
    def to_series(self) -> pd.Series: ...

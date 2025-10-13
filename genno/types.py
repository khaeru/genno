"""Types for hinting.

This module and its contents should usually be imported within an :py:`if TYPE_CHECKING`
block.
"""
# pragma: exclude file

from collections.abc import Hashable, Sequence
from typing import TypeAlias, TypeVar

from pint import Quantity, Unit
from xarray.core.types import Dims, InterpOptions, ScalarOrArray

from .core.attrseries import AttrSeries
from .core.key import Key, KeyLike
from .core.quantity import AnyQuantity
from .core.sparsedataarray import SparseDataArray

__all__ = [
    "AnyQuantity",
    "Dims",
    "IndexLabel",
    "InterpOptions",
    "KeyLike",
    "ScalarOrArray",
    "TKeyLike",
    "TQuantity",
    "Unit",
]

# Mirror the definition from pandas-stubs
IndexLabel: TypeAlias = Hashable | Sequence[Hashable]

#: Similar to :any:`KeyLike`, but as a variable that can be use to match function/method
#: outputs to inputs.
TKeyLike = TypeVar("TKeyLike", Key, str)

#: Similar to :any:`.AnyQuantity`, but as a variable that can be used to match function
#: /method outputs to inputs.
TQuantity = TypeVar("TQuantity", AttrSeries, SparseDataArray)

#: A string possibly containing a unit expression, or a :mod:`pint` objects with units.
UnitLike = str | Unit | Quantity

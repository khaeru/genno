"""Types for hinting.

This module and its contents should usually be imported within an :py:`if TYPE_CHECKING`
block.
"""
# pragma: exclude file

from collections.abc import Hashable, Sequence
from typing import TYPE_CHECKING, TypeVar, Union

from pint import Unit
from xarray.core.types import Dims, InterpOptions, ScalarOrArray

from .core.attrseries import AttrSeries
from .core.key import KeyLike
from .core.quantity import AnyQuantity
from .core.sparsedataarray import SparseDataArray

if TYPE_CHECKING:
    # TODO Remove this block once Python 3.10 is the lowest supported version
    from typing import TypeAlias

    from .core.key import Key

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
IndexLabel: "TypeAlias" = Union[Hashable, Sequence[Hashable]]

#: Similar to :any:`KeyLike`, but as a variable that can be use to match function/method
#: outputs to inputs.
TKeyLike = TypeVar("TKeyLike", "Key", str)

#: Similar to :any:`.AnyQuantity`, but as a variable that can be used to match function
#: /method outputs to inputs.
TQuantity = TypeVar("TQuantity", AttrSeries, SparseDataArray)

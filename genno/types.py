"""Types for hinting.

This module and its contents should usually be imported within an :py:`if TYPE_CHECKING`
block.
"""
# pragma: exclude file

from pint import Unit
from xarray.core.types import Dims, InterpOptions, ScalarOrArray

from .core.quantity import AnyQuantity

__all__ = [
    "AnyQuantity",
    "Dims",
    "InterpOptions",
    "ScalarOrArray",
    "Unit",
]

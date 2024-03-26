# This module should only be imported during type checking
from typing import TYPE_CHECKING  # pragma: no cover

if TYPE_CHECKING:
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

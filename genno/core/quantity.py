import sys
from typing import TYPE_CHECKING, Literal, Type, Union

from .attrseries import AttrSeries
from .base import BaseQuantity
from .sparsedataarray import SparseDataArray

if TYPE_CHECKING:
    from typing import TypeAlias


def assert_quantity(*args):
    """Assert that each of `args` is a Quantity object.

    Raises
    ------
    TypeError
        with a indicative message.
    """
    for i, arg in enumerate(args):
        if not isinstance(arg, BaseQuantity):
            raise TypeError(
                f"arg #{i+1} ({repr(arg)[:20]}) is not Quantity; likely an incorrect key"
            )


def get_class() -> Type[Union[AttrSeries, SparseDataArray]]:
    """Get the current :class:`.Quantity` implementation in use.

    Returns one of the classes :class:`.AttrSeries` or :class:`.SparseDataArray`.
    """
    global Quantity
    return Quantity


def set_class(
    name: Literal["AttrSeries", "SparseDataArray"] = "AttrSeries",
) -> Type[Union[AttrSeries, SparseDataArray]]:
    """Set the :class:`.Quantity` implementation to be used.

    This also updates :py:`genno.Quantity` and :py:`genno.quantity.Quantity` to refer to
    the selected class. It does **not** update previously-imported references to one
    class or the other; code that uses :func:`.set_class` should refer to one of those
    two locations:

    .. code-block::

       import genno
       from genno import Quantity  # AttrSeries, by default

       Quantity()        # AttrSeries
       genno.Quantity()  # AttrSeries

       genno.set_class("SparseDataArray")

       Quantity()        # AttrSeries
       genno.Quantity()  # SparseDataArray

    Another approach is to update the local reference with the return value of the
    function:

    .. code-block:: python

       from genno import Quantity, set_class

       Quantity()  # AttrSeries

       Quantity = set_class("SparseDataArray")

       Quantity()  # SparseDataArray

    In code that does not use :func:`.set_class`, :py:`from genno import Quantity` is
    safe.

    See also
    --------
    .AnyQuantity
    """
    global CLASS

    try:
        cls = {"AttrSeries": AttrSeries, "SparseDataArray": SparseDataArray}[name]
    except KeyError:
        raise ValueError(f"no Quantity implementation {name}")

    # Update globals in the current module and at the top level
    for module in "genno.core.quantity", "genno":
        setattr(sys.modules[module], "Quantity", cls)

    # Update global
    CLASS = cls.__name__

    return cls


#: Class used to implement :class:`.Quantity`.
Quantity: "TypeAlias" = AttrSeries

#: Name of :class:`.Quantity`.
CLASS = "AttrSeries"

#: Either :class:`.AttrSeries` or :class:`.SparseDataArray`. Code in :mod:`genno` or
#: user code that receives or returns any Quantity implementation should be typed with
#: this type.
AnyQuantity = Union[AttrSeries, SparseDataArray]

import operator
from abc import abstractmethod
from numbers import Number
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Generic,
    Hashable,
    Mapping,
    MutableMapping,
    Optional,
    Sequence,
    Tuple,
    TypeVar,
    Union,
)

import pandas as pd
import pint

if TYPE_CHECKING:
    from typing import Self  # Python ≥3.11

    from genno.types import Unit


class UnitsMixIn:
    """Object with :attr:`.units` and :meth:`._binary_op_units`."""

    attrs: Dict[Hashable, Any]

    @property
    # def units(self) -> "Unit":
    def units(self):
        """Retrieve or set the units of the Quantity.

        Examples
        --------
        Create a quantity without units:

        >>> qty = Quantity(...)

        Set using a string; automatically converted to pint.Unit:

        >>> qty.units = "kg"
        >>> qty.units
        <Unit('kilogram')>

        """
        return self.attrs.setdefault(
            "_unit", pint.get_application_registry().dimensionless
        )

    @units.setter
    def units(self, value: Union["Unit", str]) -> None:
        self.attrs["_unit"] = pint.get_application_registry().Unit(value)

    def _binary_op_units(self, name: str, other: "UnitsMixIn") -> Tuple["Unit", float]:
        """Determine result units for a binary operation between `self` and `other`.

        Returns:
        1. Result units.
        2. For 'add' or 'sub' operations, a scaling factor to make `other` compatible
           with `self`.
        """
        if name == "pow":
            # Currently handled by operator.pow()
            return self.units, 1.0

        # Retrieve units of `other`
        other_units = other.units

        # Ensure there is not a mix of pint.Unit and pint.registry.Unit; this throws off
        # pint's internal logic
        if other_units.__class__ is not self.units.__class__:
            other_units = self.units.__class__(other_units)

        if name in ("add", "sub"):
            # Determine multiplicative factor to align `other` to `self`
            return self.units, pint.Quantity(1.0, other_units).to(self.units).magnitude
        else:
            # Allow pint to determine the output units
            return getattr(operator, name)(self.units, other_units), 1.0


def make_binary_op(name: str):
    """Create a method for binary operator `name`."""

    swap = name.startswith("r")
    name = name[1:] if swap else name

    def method(obj: "BaseQuantity", other: "BaseQuantity"):
        scalar_other = False
        if isinstance(other, Number):
            other = type(obj)(other)
            scalar_other = True
        elif not (
            isinstance(other, type(obj))
            or getattr(other, "__thisclass__", None) is type(obj)  # super()
        ):
            raise TypeError(type(other))

        left, right, result_units, factor = prepare_binary_op(obj, other, name, swap)

        # If `other` was scalar, the units of `obj` carry to the result. Otherwise,
        # use `result_units`
        return obj._keep(
            obj._perform_binary_op(name, left, right, factor),
            units=obj.units if scalar_other else result_units,
        )

    return method


T = TypeVar("T")


class BinaryOpsMixIn(Generic[T]):
    """Binary operations for :class:`Quantity`.

    Subclasses **must** implement :meth:`_perform_binary_op`.

    Several binary operations are provided with methods that:

    - Convert scalar operands to :class:`.Quantity`.
    - Determine result units.
    - Preserve name and non-unit attrs.
    """

    __add__ = make_binary_op("add")
    __mul__ = make_binary_op("mul")
    __pow__ = make_binary_op("pow")
    __radd__ = make_binary_op("radd")
    __rmul__ = make_binary_op("rmul")
    __rtruediv__ = make_binary_op("rtruediv")
    __sub__ = make_binary_op("sub")
    __truediv__ = make_binary_op("truediv")

    @staticmethod
    @abstractmethod
    def _perform_binary_op(name: str, left: T, right: T, factor: float) -> T: ...


class BaseQuantity(
    BinaryOpsMixIn,
    UnitsMixIn,
):
    """Common base for a class that behaves like :class:`xarray.DataArray`.

    The class has units and unit-aware binary operations.
    """

    name: Optional[Hashable]

    @abstractmethod
    def __init__(
        self,
        data: Any = None,
        coords: Union[Sequence[Tuple], Mapping[Hashable, Any], None] = None,
        dims: Union[str, Sequence[Hashable], None] = None,
        name: Hashable = None,
        attrs: Optional[Mapping] = None,
        # internal parameters
        indexes: Optional[Dict[Hashable, pd.Index]] = None,
        fastpath: bool = False,
        **kwargs,
    ): ...

    def _keep(
        self,
        target: "Self",
        attrs: Optional[Any] = None,
        name: Optional[Any] = None,
        units: Optional[Any] = None,
    ) -> "Self":
        """Preserve `name`, `units`, and/or other `attrs` from `self` to `target`."""
        if name is not False:
            target.name = name or self.name
        if units is not False:
            # Only units; not other attrs
            target.units = units or self.units
        elif attrs is not False:
            target.attrs.update(attrs or self.attrs)
        return target


def prepare_binary_op(
    obj: BaseQuantity, other, name: str, swap: bool
) -> Tuple[BaseQuantity, BaseQuantity, "Unit", float]:
    """Prepare inputs for a binary operation.

    Returns:

    1. The left operand (`obj` if `swap` is False else `other`).
    2. The right operand. If units of `other` are different than `obj`, `other` is
       scaled.
    3. Units for the result. In additive operations, the units of `obj` take precedence.
    4. Any scaling factor needed to make units of `other` compatible with `obj`.
    """
    # Determine resulting units
    result_units, factor = obj._binary_op_units(name, other)

    # Apply a multiplicative factor to align units
    if factor != 1.0:
        other = super(type(obj), other).__mul__(factor)

    # For __r*__ methods
    left, right = (other, obj) if swap else (obj, other)

    return left, right, result_units, factor


def collect_attrs(
    data, attrs_arg: Optional[Mapping], kwargs: MutableMapping
) -> MutableMapping:
    """Handle `attrs` and 'units' `kwargs` to Quantity constructors."""
    # Use attrs, if any, from an existing object, if any
    new_attrs = getattr(data, "attrs", dict()).copy()

    # Overwrite with values from an explicit attrs argument
    new_attrs.update(attrs_arg or dict())

    # Store the "units" keyword argument as an attr
    units = kwargs.pop("units", None)
    if units is not None:
        new_attrs["_unit"] = pint.Unit(units)

    return new_attrs


def single_column_df(data, name: Hashable) -> Tuple[Any, Hashable]:
    """Handle `data` and `name` arguments to Quantity constructors."""
    if isinstance(data, pd.DataFrame):
        if len(data.columns) != 1:
            raise TypeError(
                f"Cannot instantiate Quantity from {len(data.columns)}-D data frame"
            )

        # Unpack a single column; use its name if not overridden by `name`
        return data.iloc[:, 0], (name or data.columns[0])
    else:
        return data, name

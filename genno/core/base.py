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
    cast,
)

import numpy as np
import pandas as pd
import pint

if TYPE_CHECKING:
    from genno.types import Unit

    from .quantity import AnyQuantity


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

    def _binary_op_units(
        self, other: "UnitsMixIn", op, swap: bool
    ) -> Tuple["Unit", float]:
        """Determine result units for a binary operation between `self` and `other`.

        Returns:
        1. Result units.
        2. For rank-1 operations ('add', 'radd', 'rsub', 'sub') operations, a scaling
           factor to make magnitudes of `other` compatible with `self`.
        """
        # Retrieve units of `other`
        ou = other.units

        # Ensure there is not a mix of pint.Unit and pint.registry.Unit; this throws off
        # pint's internal logic
        if ou.__class__ is not self.units.__class__:
            ou = self.units.__class__(ou)

        if rank(op) == 1:
            # Determine multiplicative factor to align `other` to `self`
            return self.units, pint.Quantity(1.0, ou).to(self.units).magnitude
        elif rank(op) == 2:
            # Allow pint to determine the output units
            return op(*[ou, self.units] if swap else [self.units, ou]), np.nan
        else:
            # Exponent, its units, and base units
            exp, eu, bu = (self, self.units, ou) if swap else (other, ou, self.units)
            if not eu.dimensionless:
                raise ValueError(f"Cannot raise to a power with units {eu:~}")

            # Extract the (dense) data of the exponent
            data = cast("AnyQuantity", exp).to_series().values
            # Each exponent modulo 1. Set of {0} if exponents are all integers.
            check = set(np.mod(data, 1))
            # Unique values in data
            unique_values = np.unique(data)

            if check == {0.0} and len(unique_values) == 1:
                # The same, integer exponent for all values; raise the base units to
                # this value
                return op(bu, unique_values[0]), np.nan
            else:
                return pint.get_application_registry().dimensionless, np.nan


def make_binary_op(op, *, swap: bool):
    """Create a method for binary operator `name`."""

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

        left, right, result_units, factor = prepare_binary_op(obj, other, op, swap)

        # If `other` was scalar and the operation is rank-1 (add, sub, etc.), the units
        # of `obj` carry to the result. Otherwise, use `result_units`.
        return obj._keep(
            obj._perform_binary_op(op, left, right, factor),
            name=scalar_other,
            attrs=scalar_other,
            units=obj.units if (scalar_other and rank(op) == 1) else result_units,
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

    __add__ = make_binary_op(operator.add, swap=False)
    __mul__ = make_binary_op(operator.mul, swap=False)
    __pow__ = make_binary_op(operator.pow, swap=False)
    __radd__ = make_binary_op(operator.add, swap=True)
    __rmul__ = make_binary_op(operator.mul, swap=True)
    __rpow__ = make_binary_op(operator.pow, swap=True)
    __rsub__ = make_binary_op(operator.sub, swap=True)
    __rtruediv__ = make_binary_op(operator.truediv, swap=True)
    __sub__ = make_binary_op(operator.sub, swap=False)
    __truediv__ = make_binary_op(operator.truediv, swap=False)

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
        target: "AnyQuantity",
        attrs: Optional[Any] = False,
        name: Optional[Any] = False,
        units: Optional[Any] = False,
    ) -> "AnyQuantity":
        """Preserve `name`, `units`, and/or other `attrs` from `self` to `target`.

        The action for each argument is:

        - :any:`False`: don't keep.
        - :any:`True`: keep the existing value.
        - Anything else: assign this value.
        """
        if name is not False:
            target.name = self.name if name is True else name
        if attrs is True:
            target.attrs.update(self.attrs)
        elif attrs is not False:
            assert isinstance(attrs, Mapping)
            target.attrs.update(attrs)
        if units is not False:
            # Only units; not other attrs
            target.units = self.units if units is True else units
        return target


def prepare_binary_op(
    obj: BaseQuantity, other, op, swap: bool
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
    result_units, factor = obj._binary_op_units(other, op, swap)

    # Apply a multiplicative factor to align units
    if rank(op) == 1 and factor != 1.0:
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


def rank(op) -> int:
    """Rank of the binary operation `op`.

    See `‘Hyperoperation’ on Wikipedia <https://en.wikipedia.org/wiki/Hyperoperation>`_
    for the sense of this meaning of ‘rank’.
    """
    return {
        operator.add: 1,
        operator.sub: 1,
        operator.mul: 2,
        operator.truediv: 2,
        operator.pow: 3,
    }[op]


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

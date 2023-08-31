import logging
import re
from functools import partial, singledispatchmethod
from itertools import chain, compress
from typing import Callable, Generator, Iterable, Iterator, Optional, Tuple, Union
from warnings import warn

from genno.core.quantity import Quantity

log = logging.getLogger(__name__)

#: Regular expression for valid key strings.
EXPR = re.compile(r"^(?P<name>[^:]+)(:(?P<dims>([^:-]*-)*[^:-]+)?(:(?P<tag>[^:]*))?)?$")

#: Regular expression for non-keylike strings.
BARE_STR = re.compile(r"^\s*(?P<name>[^:]+)\s*$")


class Key:
    """A hashable key for a quantity that includes its dimensionality."""

    _name: str
    _dims: Tuple[str, ...]
    _tag: Optional[str]

    def __init__(
        self,
        name_or_value: Union[str, "Key", Quantity],
        dims: Iterable[str] = [],
        tag: Optional[str] = None,
        _fast: bool = False,
    ):
        if _fast:
            # Fast path: don't handle arguments
            assert isinstance(name_or_value, str)
            self._name = name_or_value
            self._dims = tuple(dims)
            self._tag = tag or None
        else:
            self._name, _dims, _tag = self._from(name_or_value)

            # Check for conflicts between dims inferred from name_or_value and any
            # direct argument
            # TODO handle resolveable combinations without raising exceptions
            if bool(_dims) and bool(dims):
                raise ValueError(
                    f"Conflict: {dims = } argument vs. {_dims!r} from {name_or_value!r}"
                )
            elif bool(_tag) and bool(tag):
                raise ValueError(
                    f"Conflict: {tag = } argument vs. {_tag!r} from {name_or_value!r}"
                )

            self._dims = _dims or tuple(dims)
            self._tag = _tag or tag

        # Pre-compute string representation and hash
        self._str = "{}:{}{}".format(
            self._name, "-".join(self._dims), f":{self._tag}" if self._tag else ""
        )
        self._hash = hash(self._str)

    # _from() methods: convert various arguments into (name, dims, tag) tuples
    @singledispatchmethod
    @classmethod
    def _from(cls, value) -> Tuple[str, Tuple[str, ...], Optional[str]]:
        if isinstance(value, cls):
            return value._name, value._dims, value._tag
        else:
            raise TypeError(type(value))

    @_from.register
    def _(cls, value: str):
        # Parse a string
        match = EXPR.match(value)
        if match is None:
            raise ValueError(f"Invalid key expression: {repr(value)}")
        groups = match.groupdict()
        return (
            groups["name"],
            tuple() if not groups["dims"] else tuple(groups["dims"].split("-")),
            groups["tag"],
        )

    @_from.register
    def _(cls, value: Quantity):
        return str(value.name), tuple(map(str, value.dims)), None

    # Class methods

    @classmethod
    def bare_name(cls, value) -> Optional[str]:
        """If `value` is a bare name (no dims or tags), return it; else :obj:`None`."""
        if not isinstance(value, str):
            return None
        match = BARE_STR.match(value)
        return match.group("name") if match else None

    @classmethod
    def from_str_or_key(
        cls,
        value: Union[str, "Key", Quantity],
        drop: Union[Iterable[str], bool] = [],
        append: Iterable[str] = [],
        tag: Optional[str] = None,
    ) -> "Key":
        """Return a new Key from *value*.

        Parameters
        ----------
        value : str or Key
            Value to use to generate a new Key.
        drop : list of str or :obj:`True`, optional
            Existing dimensions of *value* to drop. See :meth:`drop`.
        append : list of str, optional.
            New dimensions to append to the returned Key. See :meth:`append`.
        tag : str, optional
            Tag for returned Key. If *value* has a tag, the two are joined
            using a '+' character. See :meth:`add_tag`.

        Returns
        -------
        :class:`Key`

        .. versionchanged:: 1.18.0

           Calling :meth:`from_str_or_key` with a single argument is no longer
           necessary; simply give the same `value` as an argument to :class:`Key`.

           The class method is retained for convenience when calling with multiple
           arguments. However, the following are equivalent and may be more readable:

           .. code-block:: python

              k1 = Key("foo:a-b-c:t1", drop="b", append="d", tag="t2")
              k2 = Key("foo:a-b-c:t1").drop("b").append("d)"
        """
        base = cls(value)

        # Return quickly if no further manipulations are required
        if not any([drop, append, tag]):
            warn(
                "Calling Key.from_str_or_key(value) with no other arguments is no "
                "longer necessary; simply use Key(value)",
                FutureWarning,
                stacklevel=2,
            )
            return base

        # mypy is fussy here
        drop_args: Tuple[Union[str, bool], ...] = tuple(
            [drop] if isinstance(drop, bool) else drop
        )

        # Drop and append dimensions; add tag
        return base.drop(*drop_args).append(*tuple(append)).add_tag(tag)

    @classmethod
    def product(cls, new_name: str, *keys, tag: Optional[str] = None) -> "Key":
        """Return a new Key that has the union of dimensions on *keys*.

        Dimensions are ordered by their first appearance:

        1. First, the dimensions of the first of the *keys*.
        2. Next, any additional dimensions in the second of the *keys* that
           were not already added in step 1.
        3. etc.

        Parameters
        ----------
        new_name : str
            Name for the new Key. The names of *keys* are discarded.
        """
        # Iterable of dimension names from all keys, in order, with repetitions
        dims = chain(*map(lambda k: cls(k).dims, keys))

        # Return new key. Use dict to keep only unique *dims*, in same order
        return cls(new_name, dict.fromkeys(dims).keys()).add_tag(tag)

    def __add__(self, other) -> "Key":
        if isinstance(other, str):
            return self.add_tag(other)
        else:
            raise TypeError(type(other))

    def __mul__(self, other) -> "Key":
        if isinstance(other, str):
            return self.append(other)
        else:
            raise TypeError(type(other))

    def __truediv__(self, other) -> "Key":
        if isinstance(other, str):
            return self.drop(other)
        else:
            raise TypeError(type(other))

    def __repr__(self) -> str:
        """Representation of the Key, e.g. '<name:dim1-dim2-dim3:tag>."""
        return f"<{self._str}>"

    def __str__(self) -> str:
        """Representation of the Key, e.g. 'name:dim1-dim2-dim3:tag'."""
        # Use a cache so this value is only generated once; otherwise the stored value
        # is returned. This requires that the properties of the key be immutable.
        return self._str

    def __hash__(self):
        """Key hashes the same as str(Key)."""
        return self._hash

    def __eq__(self, other) -> bool:
        """Key is equal to str(Key)."""
        try:
            other = Key(other)
        except TypeError:
            return False

        return (
            (self.name == other.name)
            and (set(self.dims) == set(other.dims))
            and (self.tag == other.tag)
        )

    # Less-than and greater-than operations, for sorting
    def __lt__(self, other) -> bool:
        if isinstance(other, Key):
            return str(self.sorted) < str(other.sorted)
        elif isinstance(other, str):
            return str(self.sorted) < other
        else:
            return NotImplemented

    def __gt__(self, other) -> bool:
        if isinstance(other, Key):
            return str(self.sorted) > str(other.sorted)
        elif isinstance(other, str):
            return str(self.sorted) > other
        else:
            return NotImplemented

    @property
    def name(self) -> str:
        """Name of the quantity, :class:`str`."""
        return self._name

    @property
    def dims(self) -> Tuple[str, ...]:
        """Dimensions of the quantity, :class:`tuple` of :class:`str`."""
        return self._dims

    @property
    def tag(self) -> Optional[str]:
        """Quantity tag, :class:`str` or :obj:`None`."""
        return self._tag

    @property
    def sorted(self) -> "Key":
        """A version of the Key with its :attr:`dims` sorted alphabetically."""
        return Key(self._name, sorted(self._dims), self._tag, _fast=True)

    def rename(self, name: str) -> "Key":
        """Return a Key with a replaced `name`."""
        return Key(name, self._dims, self._tag, _fast=True)

    def drop(self, *dims: Union[str, bool]) -> "Key":
        """Return a new Key with `dims` dropped."""
        return Key(
            self._name,
            [] if dims == (True,) else filter(lambda d: d not in dims, self._dims),
            self._tag,
            _fast=True,
        )

    def drop_all(self) -> "Key":
        """Return a new Key with all dimensions dropped / zero dimensions."""
        return Key(self._name, tuple(), self._tag, _fast=True)

    def append(self, *dims: str) -> "Key":
        """Return a new Key with additional dimensions `dims`."""
        return Key(self._name, list(self._dims) + list(dims), self._tag, _fast=True)

    def add_tag(self, tag) -> "Key":
        """Return a new Key with `tag` appended."""
        return Key(
            self._name, self._dims, "+".join(filter(None, [self._tag, tag])), _fast=True
        )

    def iter_sums(self) -> Generator[Tuple["Key", Callable, "Key"], None, None]:
        """Generate (key, task) for all possible partial sums of the Key."""
        from genno import computations

        for agg_dims, others in combo_partition(self.dims):
            yield (
                Key(self._name, agg_dims, self.tag, _fast=True),
                partial(computations.sum, dimensions=others, weights=None),
                self,
            )


#: Type shorthand for :class:`Key` or any other value that can be used as a key.
KeyLike = Union[Key, str]


def combo_partition(iterable):
    """Yield pairs of lists with all possible subsets of *iterable*."""
    # Format string for binary conversion, e.g. '04b'
    fmt = "0{}b".format(len(iterable))
    for n in range(2 ** len(iterable) - 1):
        # Two binary lists
        a, b = zip(*[(v, not v) for v in map(int, format(n, fmt))])
        yield list(compress(iterable, a)), list(compress(iterable, b))


def iter_keys(value: Union[KeyLike, Tuple[KeyLike, ...]]) -> Iterator[Key]:
    """Yield :class:`Keys <Key>` from `value`.

    Raises
    ------
    TypeError
        `value` is not an iterable of :class:`Key`.

    See also
    --------
    .Computer.add
    """
    if isinstance(value, (Key, str)):
        yield Key(value)
        tmp: Iterator[KeyLike] = iter(())
    else:
        tmp = iter(value)
    for element in tmp:
        if not isinstance(element, Key):
            raise TypeError(type(element))
        yield element


def single_key(value: Union[KeyLike, Tuple[KeyLike, ...], Iterator]) -> Key:
    """Ensure `value` is a single :class:`Key`.

    Raises
    ------
    TypeError
        `value` is not a :class:`Key` or 1-tuple of :class:`Key`.

    See also
    --------
    .Computer.add
    """
    if isinstance(value, (Key, str)):
        return Key(value)

    tmp = iter(value)
    try:
        result = next(tmp)
    except StopIteration:
        raise TypeError("Empty iterable")
    else:
        try:
            next(tmp)
        except StopIteration:
            pass
        else:
            raise TypeError("Iterable of length >1")

    if isinstance(result, Key):
        return result
    else:
        raise TypeError(type(result))

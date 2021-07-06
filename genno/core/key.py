import re
from functools import lru_cache, partial
from itertools import chain, compress
from typing import Hashable, Iterable, Optional, Tuple, Union

#: Regular expression for valid key strings.
EXPR = re.compile(r"(?P<name>[^:]+)(:(?P<dims>[^:]*)(:(?P<tag>[^:]*))?)?")


class Key:
    """A hashable key for a quantity that includes its dimensionality."""

    def __init__(self, name: str, dims: Iterable[str] = [], tag: Optional[str] = None):
        self._name = name
        self._dims = tuple(dims)
        self._tag = tag if isinstance(tag, str) and len(tag) else None

    @classmethod
    def from_str_or_key(
        cls,
        value: Union[str, "Key"],
        drop: Union[Iterable[str], bool] = [],
        append: Iterable[str] = [],
        tag: Optional[str] = None,
    ):
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
        """
        # Determine the base Key
        if isinstance(value, str):
            # Parse a string
            match = EXPR.match(value)
            if match is None:
                raise ValueError(f"Invalid key expression: {repr(value)}")
            groups = match.groupdict()
            base = cls(
                name=groups["name"],
                dims=[] if not groups["dims"] else groups["dims"].split("-"),
                tag=groups["tag"],
            )
            if any(len(dim) == 0 for dim in base.dims):
                raise ValueError(f"Invalid key expression: {repr(value)}")
        elif isinstance(value, cls):
            base = value
        else:
            raise TypeError(type(value))

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
        dims = chain(*[k.dims for k in keys])

        # Return new key. Use dict to keep only unique *dims*, in same order
        return cls(new_name, dict.fromkeys(dims).keys()).add_tag(tag)

    def __repr__(self) -> str:
        """Representation of the Key, e.g. '<name:dim1-dim2-dim3:tag>."""
        return f"<{self}>"

    def __str__(self) -> str:
        """Representation of the Key, e.g. 'name:dim1-dim2-dim3:tag'."""
        # Use a cache so this value is only generated once; otherwise the stored value
        # is returned. This requires that the properties of the key be immutable.
        @lru_cache(1)
        def _():
            return ":".join(
                [self._name, "-".join(self._dims)] + ([self._tag] if self._tag else [])
            )

        return _()

    def __hash__(self):
        """Key hashes the same as str(Key)."""

        @lru_cache(1)
        def _():
            return hash(str(self))

        return _()

    def __eq__(self, other) -> bool:
        """Key is equal to str(Key)."""
        if isinstance(other, str):
            other = Key.from_str_or_key(other)
        elif not isinstance(other, Key):
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
        return Key(self.name, sorted(self.dims), self.tag)

    def drop(self, *dims: Union[str, bool]):
        """Return a new Key with `dims` dropped."""
        if dims == (True,):
            new_dims: Iterable[str] = []
        else:
            new_dims = filter(lambda d: d not in dims, self.dims)
        return Key(self.name, new_dims, self.tag)

    def append(self, *dims: str):
        """Return a new Key with additional dimensions `dims`."""
        return Key(self.name, list(self.dims) + list(dims), self.tag)

    def add_tag(self, tag):
        """Return a new Key with `tag` appended."""
        return Key(self.name, self.dims, "+".join(filter(None, [self.tag, tag])))

    def iter_sums(self):
        """Generate (key, task) for all possible partial sums of the Key."""
        from genno import computations

        for agg_dims, others in combo_partition(self.dims):
            yield (
                Key(self.name, agg_dims, self.tag),
                partial(computations.sum, dimensions=others, weights=None),
                self,
            )


#: Type shorthand for :class:`Key` or any other value that can be used as a key.
KeyLike = Union[Key, Hashable]


def combo_partition(iterable):
    """Yield pairs of lists with all possible subsets of *iterable*."""
    # Format string for binary conversion, e.g. '04b'
    fmt = "0{}b".format(len(iterable))
    for n in range(2 ** len(iterable) - 1):
        # Two binary lists
        a, b = zip(*[(v, not v) for v in map(int, format(n, fmt))])
        yield list(compress(iterable, a)), list(compress(iterable, b))

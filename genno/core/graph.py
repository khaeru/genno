from collections.abc import Generator, Sequence
from itertools import chain, tee
from operator import itemgetter
from typing import Any, Dict, Iterable, Optional, Union

from .key import Key, KeyLike


def _key_arg(key: KeyLike) -> Union[str, Key]:
    return Key.bare_name(key) or Key.from_str_or_key(key)


class Graph(dict):
    """A dictionary for a graph indexed by :class:`.Key`.

    Graph maintains indexes on set/delete/pop/update operations that allow for fast
    lookups/member checks in certain special cases:

    .. autosummary::

       unsorted_key
       full_key

    These basic features are used to provide higher-level helpers for
    :class:`.Computer`:

    .. autosummary::

       infer
    """

    _unsorted: Dict[KeyLike, KeyLike] = dict()
    _full: Dict[Key, Key] = dict()

    def __init__(self, *args, **kwargs):
        # Initialize members
        super().__init__(*args, **kwargs)

        # Initialize indices
        self._unsorted = dict()
        self._full = dict()

        # Index new keys
        for k in kwargs.keys():
            self._index(k)

    def _index(self, key: KeyLike):
        """Add `key` to the indices."""
        k = _key_arg(key)
        if isinstance(k, Key):
            self._unsorted[k.sorted] = k
            nodim = k.drop(True)
            if len(k.dims) >= len(self._full.get(nodim, nodim).dims):
                self._full[nodim] = k
        else:
            self._unsorted[k] = key

    def _deindex(self, key: KeyLike):
        """Remove `key` from the indices."""
        k = _key_arg(key)
        if isinstance(k, Key):
            self._unsorted.pop(k.sorted, None)
            self._full.pop(k.drop(True), None)
        else:
            self._unsorted.pop(k, None)

    def __setitem__(self, key: KeyLike, value: Any):
        super().__setitem__(key, value)
        self._index(key)

    def __delitem__(self, key: KeyLike):
        super().__delitem__(key)
        self._deindex(key)

    def __contains__(self, item: KeyLike) -> bool:
        """:obj:`True` if `item` *or* a key with the same dims in a different order."""
        return super().__contains__(item) or bool(self.unsorted_key(item))

    def pop(self, *args):
        try:
            return super().pop(*args)
        finally:
            self._deindex(args[0])

    def update(self, arg=None, **kwargs):
        if isinstance(arg, (Sequence, Generator)):
            arg0, arg1 = tee(arg)
            arg_keys = map(itemgetter(0), arg0)
        else:
            arg1 = arg or dict()
            arg_keys = arg1.keys()

        for key in chain(kwargs.keys(), arg_keys):
            self._index(key)

        super().update(arg1, **kwargs)

    def unsorted_key(self, key: KeyLike) -> Optional[KeyLike]:
        """Return `key` with its original or unsorted dimensions."""
        k = _key_arg(key)
        return self._unsorted.get(k.sorted if isinstance(k, Key) else k)

    def full_key(self, name_or_key: KeyLike) -> Optional[KeyLike]:
        """Return `name_or_key` with its full dimensions."""
        return self._full.get(Key.from_str_or_key(name_or_key, drop=True))

    def infer(
        self, key: Union[str, Key], dims: Iterable[str] = []
    ) -> Optional[KeyLike]:
        """Infer a `key`.

        Parameters
        ----------
        dims : list of str, optional
            Drop all but these dimensions from the returned key(s).

        Returns
        -------
        str
            If `key` is not found in the Graph.
        Key
            `key` with either its full dimensions (cf. :meth:`full_key`) or, if `dims`
            are given, with only these dims.
        """
        result = self.unsorted_key(key) or key

        if isinstance(key, str) or not key.dims:
            # Find the full-dimensional key
            result = self.full_key(result)

        if not isinstance(result, Key):
            return result or key

        # Drop all but `dims`
        if dims:
            result = result.drop(*(set(result.dims) - set(dims)))

        return result

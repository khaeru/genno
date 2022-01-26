import logging
from functools import partial
from importlib import import_module
from inspect import signature
from itertools import chain, compress, repeat
from operator import itemgetter
from pathlib import Path
from types import ModuleType
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    MutableSequence,
    Optional,
    Tuple,
    Union,
    cast,
)
from warnings import warn

import dask
import pint
from dask import get as dask_get  # NB dask.threaded.get causes JPype to segfault
from dask.optimization import cull

from genno import caching, computations
from genno.util import partial_split

from .describe import describe_recursive
from .exceptions import ComputationError, KeyExistsError, MissingKeyError
from .key import Key, KeyLike

log = logging.getLogger(__name__)


class Computer:
    """Class for describing and executing computations.

    Parameters
    ----------
    kwargs :
        Passed to :meth:`configure`.
    """

    #: A dask-format graph (see :doc:`1 <dask:graphs>`, :doc:`2 <dask:spec>`).
    graph: Dict[str, Any] = {"config": {}}

    #: The default key to :meth:`.get` with no argument.
    default_key = None

    # An index of key names -> full keys.
    _index: Dict[str, Key] = {}

    #: List of modules containing pre-defined computations.
    #:
    #: By default, this includes the :mod:`genno` built-in computations in
    #: :mod:`genno.computations`. :meth:`require_compat` appends additional modules,
    #: e.g. #: :mod:`.compat.pyam.computations`, to this list. User code may also add
    #: modules to this list.
    modules: MutableSequence[ModuleType] = [computations]

    def __init__(self, **kwargs):
        self.graph = {"config": {}}
        self._index = {}
        self.configure(**kwargs)

    def configure(
        self, path: Union[Path, str] = None, fail: Union[str, int] = "raise", **config
    ):
        """Configure the Computer.

        Accepts a `path` to a configuration file and/or keyword arguments.
        Configuration keys loaded from file are superseded by keyword arguments.
        Messages are logged at level :data:`logging.INFO` if `config` contains
        unhandled sections.

        See :doc:`config` for a list of all configuration sections and keys, and details
        of the configuration file format.

        Parameters
        ----------
        path : .Path, optional
            Path to a configuration file in JSON or YAML format.
        fail : "raise" or str or :mod:`logging` level, optional
            Passed to :meth:`.add_queue`. If not "raise", then log messages are
            generated for config handlers that fail. The Computer may be only partially
            configured.
        **config :
            Configuration keys/sections and values.
        """

        from genno.config import parse_config

        # Maybe load from a path
        if path:
            config["path"] = Path(path)

        parse_config(self, data=config, fail=fail)

    def get_comp(self, name) -> Optional[Callable]:
        """Return a computation function.

        :meth:`get_comp` checks each of the :attr:`modules` for a function or callable
        with the given `name`. Modules at the end of the list take precedence over those
        earlier in the lists.

        Returns
        -------
        .callable
        None
            If there is no computation with the given `name` in any of :attr:`modules`.
        """
        for module in reversed(self.modules):
            try:
                return getattr(module, name)
            except AttributeError:
                continue  # `name` not in this module
            except TypeError:
                return None  # `name` is not a string; can't be the name of a function
        return None

    def require_compat(self, pkg: str):
        """Load computations from ``genno.compat.{pkg}`` for use with :func:`.get_comp`.

        The specified module is appended to :attr:`modules`.

        Raises
        ------
        ModuleNotFoundError
            If the required packages are missing.

        See also
        --------
        .get_comp
        """
        name = f"genno.compat.{pkg}"
        if not getattr(import_module(name), f"HAS_{pkg.upper()}"):
            raise ModuleNotFoundError(
                f"No module named '{pkg}', required by genno.compat.{pkg}"
            )
        self.modules = list(self.modules) + [import_module(f"{name}.computations")]

    def add(self, data, *args, **kwargs):
        """General-purpose method to add computations.

        :meth:`add` can be called in several ways; its behaviour depends on `data`; see
        below. It chains to methods such as :meth:`add_single`, :meth:`add_queue`,
        and/or :meth:`apply`; each can also be called directly.

        Returns
        -------
        list of Key-like
            Some or all of the keys added to the Computer.

        See also
        ---------
        add_single
        add_queue
        apply
        """
        if isinstance(data, list):
            # A list. Use add_queue to add
            return self.add_queue(data, *args, **kwargs)

        elif isinstance(data, str) and self.get_comp(data):
            # *data* is the name of a pre-defined computation
            name = data

            if hasattr(self, f"add_{name}"):
                # Use a method on the current class to add. This invokes any
                # argument-handling conveniences, e.g. Computer.add_product()
                # instead of using the bare product() computation directly.
                return getattr(self, f"add_{name}")(*args, **kwargs)
            else:
                # Get the function directly
                func = self.get_comp(name)
                # Rearrange arguments: key, computation function, args, …
                func, kwargs = partial_split(func, kwargs)
                return self.add(args[0], func, *args[1:], **kwargs)

        elif isinstance(data, str) and data in dir(self):
            # Name of another method, e.g. 'apply'
            return getattr(self, data)(*args, **kwargs)

        elif isinstance(data, (str, Key)):
            # *data* is a key, *args* are the computation
            key, computation = data, args

            if kwargs.pop("sums", False):
                # Convert *key* to a Key object in order to use .iter_sums()
                key = Key.from_str_or_key(key)

                # Iterable of computations
                # print((tuple([key] + list(computation)), kwargs))
                # print([(c, {}) for c in key.iter_sums()])
                to_add = chain(
                    # The original
                    [(tuple([key] + list(computation)), kwargs)],
                    # One entry for each sum
                    [(c, {}) for c in key.iter_sums()],
                )

                return self.add_queue(to_add)
            else:
                # Add a single computation (without converting to Key)
                return self.add_single(key, *computation, **kwargs)
        else:
            # Some other kind of input
            raise TypeError(f"{type(data)} `data` argument")

    def cache(self, func):
        """Decorate `func` so that its return value is cached.

        See also
        --------
        :doc:`cache`
        """
        return caching.decorate(func, computer=self)

    def add_queue(
        self,
        queue: Iterable[Tuple[Tuple, Mapping]],
        max_tries: int = 1,
        fail: Union[str, int] = None,
    ) -> Tuple[KeyLike, ...]:
        """Add tasks from a list or `queue`.

        Parameters
        ----------
        queue : iterable of 2-:class:`tuple`
            The members of each tuple are the arguments (e.g. :class:`list` or tuple)
            and keyword arguments (e.g :class:`dict`) to :meth:`add`.
        max_tries : int, optional
            Retry adding elements up to this many times.
        fail : "raise" or str or :mod:`logging` level, optional
            Action to take when a computation from `queue` cannot be added after
            `max_tries`: "raise" an exception, or log messages on the indicated level
            and continue.
        """
        if isinstance(fail, str):
            # Convert a string like 'debug' to logging.DEBUG
            fail = getattr(logging, fail.upper(), fail)

        if fail is not None:
            pop_level = True  # Remove this value at the end of this (outer) call
            self._queue_fail_log_level = fail
        else:
            # No value given: use the instance property from an outer call, else "raise"
            fail = getattr(self, "_queue_fail_log_level", "raise")
            pop_level = False

        # Elements to retry: list of (tries, args, kwargs)
        retry: List[Tuple[int, Tuple[Tuple, Mapping]]] = []
        added: List[KeyLike] = []

        # Iterate over elements from queue, then from retry. On the first pass,
        # count == 1; on subsequent passes, it is incremented.
        for count, (args, kwargs) in chain(zip(repeat(1), queue), retry):
            try:
                # Recurse
                key_or_keys = self.add(*args, **kwargs)
            except KeyError as exc:
                # Adding failed

                # Information for debugging
                info = [
                    f"Failed {count} times to add:",
                    f"    ({repr(args)}, {repr(kwargs)})",
                    f"    with {repr(exc)}",
                ]

                def _log(level):
                    [log.log(level, i) for i in info]

                if count < max_tries:
                    # This may only be due to items being out of order; retry silently
                    retry.append((count + 1, (args, kwargs)))
                    # _log(logging.DEBUG)  # verbose: uncomment for debugging only
                else:
                    # More than `max_tries` failures; something has gone wrong
                    if fail == "raise":
                        _log(logging.ERROR)
                        raise
                    else:
                        _log(fail)
            else:
                if isinstance(key_or_keys, tuple):
                    added.extend(key_or_keys)
                else:
                    added.append(key_or_keys)

        if pop_level:  # End of the outer call
            delattr(self, "_queue_fail_log_level")

        return tuple(added)

    # Generic graph manipulations
    def add_single(self, key, *computation, strict=False, index=False):
        """Add a single `computation` at `key`.

        Parameters
        ----------
        key : str or Key or hashable
            A string, Key, or other value identifying the output of `computation`.
        computation : object
            Any computation. See :attr:`graph`.
        strict : bool, optional
            If True, `key` must not already exist in the Computer, and any keys
            referred to by `computation` must exist.
        index : bool, optional
            If True, `key` is added to the index as a full-resolution key, so it can be
            later retrieved with :meth:`full_key`.

        Raises
        ------
        KeyExistsError
            If `strict` is :obj:`True` and either (a) `key` already exists; or (b)
            `sums` is :obj:`True` and the key for one of the partial sums of `key`
            already exists.
        MissingKeyError
            If `strict` is :obj:`True` and any key referred to by `computation` does
            not exist.
        """
        if len(computation) == 1:
            # Unpack a length-1 tuple
            computation = computation[0]

        key = maybe_convert_str(key)

        if strict or index:
            # String equivalent of `key` with all dimensions dropped, but name and tag
            # retained, e.g. "foo::bar" for "foo:a-b:bar"; but "foo" for "foo:a-b"
            idx = str(Key.from_str_or_key(key, drop=True)).rstrip(":")

        if strict:
            # Check the target key
            try:
                # Check without dim order permutations
                assert self.check_keys(key, action="return", _permute=False) is None
                # Check that `key` is not indexed, possibly with different dim order
                assert self._index.get(idx, None) != key
            except AssertionError:
                # Key already exists in graph
                raise KeyExistsError(key) from None

            # Check valid keys in `computation` and maybe rewrite
            computation = self._rewrite_comp(computation)

        if index:
            # Add `key` to the index
            self._index[idx] = key

        # Add to the graph
        self.graph[key] = computation

        return key

    def _rewrite_comp(self, computation):
        """Check and rewrite `computation`.

        If `computation` is :class:`tuple` or :class:`list`, it may contain other keys
        that :mod:`dask` must locate in the :attr:`graph`. Check these using
        :meth:`check_keys`, and return a modified `computation` with these in exactly
        the form they appear in the graph. This ensures dask can locate them for
        :meth:`get` and :meth:`describe`.
        """
        if not isinstance(computation, (list, tuple)):
            # Something else, e.g. pd.DataFrame or a literal
            return computation

        # True if the element is key-like
        is_keylike = list(map(lambda e: isinstance(e, (str, Key)), computation))

        # Run only the key-like elements through check_keys(); make an iterator
        checked = iter(self.check_keys(*compress(computation, is_keylike)))

        # Assemble the result using either checked keys (with properly ordered
        # dimensions) or unmodified elements from `computation`; cast to the same type
        return type(computation)(
            [
                next(checked) if is_keylike[i] else elem
                for i, elem in enumerate(computation)
            ]
        )

    def apply(self, generator, *keys, **kwargs):
        """Add computations by applying `generator` to `keys`.

        Parameters
        ----------
        generator : callable
            Function to apply to `keys`.
        keys : hashable
            The starting key(s).
        kwargs
            Keyword arguments to `generator`.
        """
        args = self.check_keys(*keys)

        try:
            # Inspect the generator function
            par = signature(generator).parameters
            # Name of the first parameter
            par_0 = list(par.keys())[0]
        except IndexError:
            pass  # No parameters to generator
        else:
            if issubclass(par[par_0].annotation, Computer):
                # First parameter wants a reference to the Computer object
                args.insert(0, self)

        # Call the generator. Might return None, or yield some computations
        applied = generator(*args, **kwargs)

        if applied:
            # Update the graph with the computations
            self.graph.update(applied)

    def get(self, key=None):
        """Execute and return the result of the computation `key`.

        Only `key` and its dependencies are computed.

        Parameters
        ----------
        key : str, optional
            If not provided, :attr:`default_key` is used.

        Raises
        ------
        ValueError
            If `key` and :attr:`default_key` are both :obj:`None`.
        """
        if key is None:
            if self.default_key is not None:
                key = self.default_key
            else:
                raise ValueError("no default reporting key set")
        else:
            key = self.check_keys(key)[0]

        # Protect 'config' dict, so that dask schedulers do not try to interpret its
        # contents as further tasks. Workaround for
        # https://github.com/dask/dask/issues/3523
        self.graph["config"] = dask.core.quote(self.graph.get("config", dict()))

        # Cull the graph, leaving only those needed to compute *key*
        dsk, deps = cull(self.graph, key)
        log.debug(f"Cull {len(self.graph)} -> {len(dsk)} keys")

        try:
            result = dask_get(dsk, key)
        except Exception as exc:
            raise ComputationError(exc) from None
        else:
            return result
        finally:
            self.graph["config"] = self.graph["config"][0].data

    def keys(self):
        """Return the keys of :attr:`graph`."""
        return self.graph.keys()

    def full_key(self, name_or_key):
        """Return the full-dimensionality key for `name_or_key`.

        An quantity 'foo' with dimensions (a, c, n, q, x) is available in the Computer
        as ``'foo:a-c-n-q-x'``. This :class:`.Key` can be retrieved with::

            c.full_key("foo")
            c.full_key("foo:c")
            # etc.
        """
        name = str(Key.from_str_or_key(name_or_key, drop=True)).rstrip(":")
        return self._index[name]

    def check_keys(
        self, *keys: Union[str, Key], action="raise", _permute=True
    ) -> Optional[List[Union[str, Key]]]:
        """Check that `keys` are in the Computer.

        If any of `keys` is not in the Computer and `action` is "raise" (the default)
        :class:`KeyError` is raised. Otherwise, a list is returned with either the key
        from `keys`, or the corresponding :meth:`full_key`.

        If `action` is "return" (or any other value), :class:`None` is returned on
        missing keys.
        """
        # Sequence of graph keys, for indexing
        # TODO cache this somehow, refresh when .graph is altered
        all_keys = tuple(self.graph.keys())

        def _check(value):
            if value in self._index:
                # Add the full key
                return self._index[value]

            if value in self.graph:
                # Add the key directly. Use the key from `self.graph` to preserve
                # dimension order.
                return all_keys[all_keys.index(value)]

            # Possibly convert a string to a Key
            value = maybe_convert_str(value)
            if isinstance(value, str) or not _permute:
                return None

            # Try permutations of dimensions
            for k in filter(self.graph.__contains__, value.permute_dims()):
                result = all_keys[all_keys.index(k)]
                return result

            return None

        # Process all keys to produce more useful error messages
        result = list(map(_check, keys))

        if result.count(None):
            if action == "raise":
                # 1 or more keys missing
                # Suppress traceback from within this function
                __tracebackhide__ = True

                # Identify values in `keys` corresponding to None in `result`
                raise MissingKeyError(
                    *map(
                        itemgetter(0), filter(lambda i: i[1] is None, zip(keys, result))
                    )
                )
            else:
                return None

        return result

    def infer_keys(self, key_or_keys, dims=[]):
        """Infer complete `key_or_keys`.

        Parameters
        ----------
        dims : list of str, optional
            Drop all but these dimensions from the returned key(s).
        """
        single = isinstance(key_or_keys, (str, Key))

        result = []

        for k in [key_or_keys] if single else key_or_keys:
            # Has some dimensions or tag
            key = Key.from_str_or_key(k) if ":" in k else k

            if "::" in k or key not in self or (isinstance(key, str) and dims):
                # Find the full-dimensional key
                key = self.full_key(key)

            # Drop all but `dims`
            if dims:
                key = key.drop(*(set(key.dims) - set(dims)))

            result.append(key)

        return result[0] if single else tuple(result)

    def __contains__(self, name):
        # First check using hash (fast), then using comparison (slower) for same key
        # with dimensions in different order
        return name in self.graph or any(
            map(self.graph.__contains__, Key.from_str_or_key(name).permute_dims())
        )

    # Convenience methods
    def add_product(self, key, *quantities, sums=True):
        """Add a computation that takes the product of *quantities*.

        Parameters
        ----------
        key : str or Key
            Key of the new quantity. If a Key, any dimensions are ignored; the
            dimensions of the product are the union of the dimensions of
            *quantities*.
        sums : bool, optional
            If :obj:`True`, all partial sums of the new quantity are also
            added.

        Returns
        -------
        :class:`Key`
            The full key of the new quantity.
        """
        # Fetch the full key for each quantity
        base_keys = list(map(Key.from_str_or_key, self.check_keys(*quantities)))

        # Compute a key for the result
        # Parse the name and tag of the target
        key = Key.from_str_or_key(key)
        # New key with dimensions of the product
        key = Key.product(key.name, *base_keys, tag=key.tag)

        # Add the basic product to the graph and index
        keys = self.add(key, computations.product, *base_keys, sums=sums, index=True)

        return keys[0]

    def aggregate(self, qty, tag, dims_or_groups, weights=None, keep=True, sums=False):
        """Add a computation that aggregates *qty*.

        Parameters
        ----------
        qty: :class:`Key` or str
            Key of the quantity to be aggregated.
        tag: str
            Additional string to add to the end the key for the aggregated
            quantity.
        dims_or_groups: str or iterable of str or dict
            Name(s) of the dimension(s) to sum over, or nested dict.
        weights : :class:`xarray.DataArray`, optional
            Weights for weighted aggregation.
        keep : bool, optional
            Passed to :meth:`computations.aggregate <genno.computations.aggregate>`.
        sums : bool, optional
            Passed to :meth:`add`.

        Returns
        -------
        :class:`Key`
            The key of the newly-added node.
        """
        # TODO maybe split this to two methods?

        if isinstance(dims_or_groups, dict):
            groups = dims_or_groups
            if len(groups) > 1:
                raise NotImplementedError("aggregate() along >1 dimension")

            key = Key.from_str_or_key(qty, tag=tag)
            comp = (computations.aggregate, qty, dask.core.quote(groups), keep)
        else:
            dims = dims_or_groups
            if isinstance(dims, str):
                dims = [dims]

            key = Key.from_str_or_key(qty, drop=dims, tag=tag)
            comp = (partial(computations.sum, dimensions=dims), qty, weights)

        return self.add(key, comp, strict=True, index=True, sums=sums)

    add_aggregate = aggregate

    def disaggregate(self, qty, new_dim, method="shares", args=[]):
        """Add a computation that disaggregates `qty` using `method`.

        Parameters
        ----------
        qty: hashable
            Key of the quantity to be disaggregated.
        new_dim: str
            Name of the new dimension of the disaggregated variable.
        method: callable or str
            Disaggregation method. If a callable, then it is applied to `var` with any
            extra `args`. If a string, then a method named 'disaggregate_{method}' is
            used.
        args: list, optional
            Additional arguments to the `method`. The first element should be the key
            for a quantity giving shares for disaggregation.

        Returns
        -------
        :class:`Key`
            The key of the newly-added node.
        """
        # Compute the new key
        key = Key.from_str_or_key(qty, append=new_dim)

        # Get the method
        if isinstance(method, str):
            try:
                method = getattr(computations, "disaggregate_{}".format(method))
            except AttributeError:
                raise ValueError(
                    "No disaggregation method 'disaggregate_{}'".format(method)
                )
        if not callable(method):
            raise TypeError(method)

        return self.add(key, tuple([method, qty] + args), strict=True)

    def add_file(self, path, key=None, **kwargs):
        """Add exogenous quantities from *path*.

        Computing the `key` or using it in other computations causes `path` to
        be loaded and converted to :class:`.Quantity`.

        Parameters
        ----------
        path : os.PathLike
            Path to the file, e.g. '/path/to/foo.ext'.
        key : str or .Key, optional
            Key for the quantity read from the file.

        Other parameters
        ----------------
        dims : dict or list or set
            Either a collection of names for dimensions of the quantity, or a
            mapping from names appearing in the input to dimensions.
        units : str or pint.Unit
            Units to apply to the loaded Quantity.

        Returns
        -------
        .Key
            Either `key` (if given) or e.g. ``file:foo.ext`` based on the `path` name,
            without directory components.

        See also
        --------
        genno.computations.load_file
        """
        path = Path(path)
        key = key if key else "file:{}".format(path.name)
        return self.add(
            key, (partial(self.get_comp("load_file"), path, **kwargs),), strict=True
        )

    # Use add_file as a helper for computations.load_file
    add_load_file = add_file

    def describe(self, key=None, quiet=True):
        """Return a string describing the computations that produce `key`.

        If `key` is not provided, all keys in the Computer are described.

        Unless `quiet`, the string is also printed to the console.

        Returns
        -------
        str
            Description of computations.
        """
        if key is None:
            # Sort with 'all' at the end
            key = tuple(
                sorted(filter(lambda k: k != "all", self.graph.keys())) + ["all"]
            )
        else:
            key = tuple(self.check_keys(key))

        result = describe_recursive(self.graph, key)
        if not quiet:
            print(result, end="\n")
        return result

    def visualize(self, filename, **kwargs):
        """Generate an image describing the Computer structure.

        This is a shorthand for :meth:`dask.visualize`. Requires
        `graphviz <https://pypi.org/project/graphviz/>`__.
        """
        return dask.visualize(self.graph, filename=filename, **kwargs)

    def write(self, key, path):
        """Write the result of `key` to the file `path`."""
        # Call the method directly without adding it to the graph
        key = self.check_keys(key)[0]
        self.get_comp("write_report")(self.get(key), path)

    @property
    def unit_registry(self):
        """The :meth:`pint.UnitRegistry` used by the Computer."""
        return pint.get_application_registry()

    # For .compat.pyam

    # "/, " requires Python 3.8; change only if/when support for Python 3.7 is dropped
    # def convert_pyam(self, quantities, tag="iamc", /, **kwargs):
    def convert_pyam(self, quantities, tag="iamc", **kwargs):
        """Add conversion of one or more **quantities** to IAMC format.

        Parameters
        ----------
        quantities : str or Key or list of (str, Key)
            Keys for quantities to transform.
        tag : str, optional
            Tag to append to new Keys.

        Other parameters
        ----------------
        kwargs :
            Any keyword arguments accepted by :func:`.as_pyam`.

        Returns
        -------
        list of Key
            Each task converts a :class:`.Quantity` into a :class:`pyam.IamDataFrame`.

        See also
        --------
        .as_pyam
        """
        self.require_compat("pyam")

        # Handle single vs. iterable of inputs
        multi_arg = not isinstance(quantities, (str, Key))
        if not multi_arg:
            quantities = [quantities]

        if len(kwargs.get("replace", {})) and not isinstance(
            next(iter(kwargs["replace"].values())), dict
        ):
            kwargs["replace"] = dict(variable=kwargs.pop("replace"))
            warn(
                f"replace must be nested dict(), e.g. {repr(kwargs['replace'])}",
                DeprecationWarning,
            )

        # Check keys
        quantities = self.check_keys(*quantities)

        # The callable for the task. If pyam is not available, require_compat() above
        # will fail; so this will never be None
        comp = partial(cast(Callable, self.get_comp("as_pyam")), **kwargs)

        keys = []
        for qty in quantities:
            # Key for the input quantity
            key = Key.from_str_or_key(qty)

            # Key for the task
            keys.append(":".join([key.name, tag]))

            # Add the task and store the key
            self.add_single(keys[-1], (comp, "scenario", key))

        return tuple(keys) if multi_arg else keys[0]

    # Use convert_pyam as a helper for computations.as_pyam
    add_as_pyam = convert_pyam


def maybe_convert_str(key):
    """Maybe convert `key` into a Key object.

    Allow a string like "foo" with no dimensions or tag to remain as-is.
    """
    _key = Key.from_str_or_key(key)
    return _key if (_key.dims or _key.tag) else key

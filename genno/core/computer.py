# Scenario reporting.
#
# Implementation notes:
#
# The core design pattern uses dask graphs; see
# http://docs.dask.org/en/latest/spec.html
# - Computer.graph is a dictionary where:
#   - keys are strings or genno.key.Key objects (which compare/hash
#     equal to their str() representation), and
#   - values are 'computations' (the Computer.add() docstring repeats the
#     definition of computations from the above URL).
# - The results of 'internal' computations are genno.utils.Quantity
#   objects.
#   - These resemble xarray.DataArray, but currently are genno.utils.
#     AttrSeries, which duck-types DataArray. This is because many ixmp/
#     message_ix quantities are large and sparse, and creating sparse
#     DataArrays is non-trivial; see https://stackoverflow.com/q/56396122/
#   - Internal computations have .attr['_unit'] describing the units of the
#     quantity, to carry these through calculations.
#
# - Always call pint.get_application_registry() from *within* functions
#   (instead of in global scope); this allows downstream code to change which
#   registry is used.
#   - The top-level methods pint.Quantity() and pint.Unit() can also be used;
#     these use the application registry.

import logging
from functools import partial
from importlib import import_module
from inspect import signature
from itertools import chain, repeat
from pathlib import Path
from types import ModuleType
from typing import Callable, Dict, Optional, Sequence, Union, cast

import dask
import pint
from dask import get as dask_get  # NB dask.threaded.get causes JPype to segfault
from dask.optimization import cull

from genno import computations
from genno.util import partial_split

from . import _config_args, configure
from .describe import describe_recursive
from .exceptions import ComputationError, KeyExistsError, MissingKeyError
from .key import Key

log = logging.getLogger(__name__)


class Computer:
    """Class for describing and executing computations.

    Parameters
    ----------
    kwargs :
        Passed to :meth:`configure`.
    """

    # TODO meet the requirements:
    # A3iii. Interpolation.

    #: A dask-format :doc:`graph <graphs>`.
    graph: Dict[str, Union[str, dict]] = {"config": {}}

    #: The default key to compute for :meth:`.get` with no argument.
    default_key = None

    # An index of key names -> full keys
    _index: Dict[str, Key] = {}

    #: List of modules containing pre-defined computations. By default, this includes
    #: the :mod:`genno` built-in computations in :mod:`genno.computations`.
    modules: Sequence[ModuleType] = [computations]

    def __init__(self, **kwargs):
        self.graph = {"config": {}}
        self._index = {}
        self.configure(**kwargs)

    def configure(self, path=None, **config):
        """Configure the Computer.

        Accepts a *path* to a configuration file and/or keyword arguments.
        Configuration keys loaded from file are replaced by keyword arguments.

        Valid configuration keys include:

        - *default*: the default key; sets :attr:`default_key`.
        - *filters*: a :class:`dict`, passed to :meth:`set_filters`.
        - *files*: a :class:`list` where every element is a :class:`dict`
          of keyword arguments to :meth:`add_file`.
        - *alias*: a :class:`dict` mapping aliases to original keys.

        Warns
        -----
        UserWarning
            If *config* contains unrecognized keys.
        """
        # Maybe load from a path
        config = _config_args(path, config)

        # Pass to global configuration
        configure(None, **config)

        # Store all configuration in the graph itself
        self.graph["config"] = config.copy()

        # Read sections

        # Default key
        try:
            self.default_key = config["default"]
        except KeyError:
            pass

        # Files with exogenous data
        for item in config.get("files", []):
            path = Path(item["path"])
            if not path.is_absolute():
                # Resolve relative paths relative to the directory containing
                # the configuration file
                path = config.get("config_dir", Path.cwd()) / path
            item["path"] = path

            self.add_file(**item)

        # Aliases
        for alias, original in config.get("alias", {}).items():
            self.add(alias, original)

        return self  # to allow chaining

    def _get_comp(self, name) -> Optional[Callable]:
        """Return a computation with the given `name`, or :obj:`None`."""
        for module in reversed(self.modules):
            try:
                return getattr(module, name)
            except AttributeError:
                continue  # `name` not in this module
            except TypeError:
                return None  # `name` is not a string; can't be the name of a function
        return None

    def _require_compat(self, pkg: str):
        name = f"genno.compat.{pkg}"
        if not getattr(import_module(name), f"HAS_{pkg.upper()}"):
            raise ModuleNotFoundError(
                f"No module named '{pkg}', required by genno.compat.{pkg}"
            )
        self.modules = list(self.modules) + [import_module(f"{name}.computations")]

    def add(self, data, *args, **kwargs):
        """General-purpose method to add computations.

        :meth:`add` can be called in several ways; its behaviour depends on
        `data`; see below. It chains to methods such as :meth:`add_single`,
        :meth:`add_queue`, and :meth:`apply`, which can also be called
        directly.

        Parameters
        ----------
        data, args : various

        Other parameters
        ----------------
        sums : bool, optional
            If :obj:`True`, all partial sums of the key `data` are also added
            to the Computer.

        Returns
        -------
        list of Key-like
            Some or all of the keys added to the Computer.

        Raises
        ------
        KeyError
            If a target key is already in the Computer; any key referred to by
            a computation does not exist; or ``sums=True`` and the key for one
            of the partial sums of `key` is already in the Computer.

        See also
        ---------
        add_single
        add_queue
        apply
        """
        if isinstance(data, list):
            # A list. Use add_queue to add
            return self.add_queue(data, *args, **kwargs)

        elif isinstance(data, str) and self._get_comp(data):
            # *data* is the name of a pre-defined computation
            name = data

            if hasattr(self, f"add_{name}"):
                # Use a method on the current class to add. This invokes any
                # argument-handling conveniences, e.g. Computer.add_product()
                # instead of using the bare product() computation directly.
                return getattr(self, f"add_{name}")(*args, **kwargs)
            else:
                # Get the function directly
                func = self._get_comp(name)
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
            raise TypeError(data)

    def add_queue(self, queue, max_tries=1, fail="raise"):
        """Add tasks from a list or `queue`.

        Parameters
        ----------
        queue : list of 2-tuple
            The members of each tuple are the arguments (i.e. a list or tuple) and
            keyword arguments (i.e. a dict) to :meth:`add`.
        max_tries : int, optional
            Retry adding elements up to this many times.
        fail : 'raise' or log level, optional
            Action to take when a computation from `queue` cannot be added after
            `max_tries`.
        """
        # Elements to retry: list of (tries, args, kwargs)
        retry = []
        added = []

        # Iterate over elements from queue, then from retry. On the first pass,
        # count == 1; on subsequent passes, it is incremented.
        for count, (args, kwargs) in chain(zip(repeat(1), queue), retry):
            try:
                # Recurse
                added.append(self.add(*args, **kwargs))
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
                    _log(logging.DEBUG)
                    # This may only be due to items being out of order, so
                    # retry silently
                    retry.append((count + 1, (args, kwargs)))
                else:
                    # More than *max_tries* failures; something has gone wrong
                    if fail == "raise":
                        _log(logging.ERROR)
                        raise
                    else:
                        _log(
                            getattr(logging, fail.upper())
                            if isinstance(fail, str)
                            else fail
                        )

        return added

    # Generic graph manipulations
    def add_single(self, key, *computation, strict=False, index=False):
        """Add a single *computation* at *key*.

        Parameters
        ----------
        key : str or Key or hashable
            A string, Key, or other value identifying the output of *task*.
        computation : object
            Any dask computation, i.e. one of:

            1. any existing key in the Computer.
            2. any other literal value or constant.
            3. a task, i.e. a tuple with a callable followed by one or more
               computations.
            4. A list containing one or more of #1, #2, and/or #3.

        strict : bool, optional
            If True, *key* must not already exist in the Computer, and any keys
            referred to by *computation* must exist.
        index : bool, optional
            If True, *key* is added to the index as a full-resolution key, so it can be
            later retrieved with :meth:`full_key`.
        """
        if len(computation) == 1:
            # Unpack a length-1 tuple
            computation = computation[0]

        if strict:
            if key in self.graph:
                # Key already exists in graph
                raise KeyExistsError(key)

            # Check that keys used in *comp* are in the graph
            keylike = filter(lambda e: isinstance(e, (str, Key)), computation)
            self.check_keys(*keylike)

        if index:
            # String equivalent of *key* with all dimensions dropped, but name
            # and tag retained
            idx = str(Key.from_str_or_key(key, drop=True)).rstrip(":")

            # Add *key* to the index
            self._index[idx] = key

        # Add to the graph
        self.graph[key] = computation

        return key

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
        """Execute and return the result of the computation *key*.

        Only *key* and its dependencies are computed.

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

        # Cull the graph, leaving only those needed to compute *key*
        dsk, deps = cull(self.graph, key)
        log.debug("Cull {} -> {} keys".format(len(self.graph), len(dsk)))

        try:
            # Protect 'config' dict, so that dask schedulers do not try to
            # interpret its contents as further tasks. Workaround for
            # https://github.com/dask/dask/issues/3523
            dsk["config"] = dask.core.quote(dsk["config"])
        except KeyError:
            pass

        try:
            return dask_get(dsk, key)
        except Exception as exc:
            raise ComputationError(exc) from None

    def keys(self):
        """Return the keys of :attr:`graph`."""
        return self.graph.keys()

    def full_key(self, name_or_key):
        """Return the full-dimensionality key for *name_or_key*.

        An quantity 'foo' with dimensions (a, c, n, q, x) is available in the Computer
        as ``'foo:a-c-n-q-x'``. This :class:`.Key` can be retrieved with::

            c.full_key("foo")
            c.full_key("foo:c")
            # etc.
        """
        name = str(Key.from_str_or_key(name_or_key, drop=True)).rstrip(":")
        return self._index[name]

    def check_keys(self, *keys):
        """Check that *keys* are in the Computer.

        If any of *keys* is not in the Computer, KeyError is raised.
        Otherwise, a list is returned with either the key from *keys*, or the
        corresponding :meth:`full_key`.
        """
        result = []
        missing = []

        # Process all keys to produce more useful error messages
        for key in keys:
            # Add the key directly if it is in the graph
            if key in self.graph:
                result.append(key)
                continue

            # Try adding the full key
            try:
                result.append(self._index[key])
            except KeyError:
                missing.append(key)

        if len(missing):
            raise MissingKeyError(*missing)

        return result

    def __contains__(self, name):
        return name in self.graph

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
            comp = (computations.aggregate, qty, groups, keep)
        else:
            dims = dims_or_groups
            if isinstance(dims, str):
                dims = [dims]

            key = Key.from_str_or_key(qty, drop=dims, tag=tag)
            comp = (partial(computations.sum, dimensions=dims), qty, weights)

        return self.add(key, comp, strict=True, index=True, sums=sums)

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
            Either `key` (if given) or e.g. ``file:foo.ext`` based on the
            `path` name, without directory components.

        See also
        --------
        genno.computations.load_file
        """
        path = Path(path)
        key = key if key else "file:{}".format(path.name)
        return self.add(
            key, (partial(self._get_comp("load_file"), path, **kwargs),), strict=True
        )

    # Use add_file as a helper for computations.load_file
    add_load_file = add_file

    def describe(self, key=None, quiet=True):
        """Return a string describing the computations that produce *key*.

        If *key* is not provided, all keys in the Computer are described.

        The string can be printed to the console, if not *quiet*.
        """
        if key is None:
            # Sort with 'all' at the end
            key = tuple(
                sorted(filter(lambda k: k != "all", self.graph.keys())) + ["all"]
            )
        else:
            key = (key,)

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
        self._get_comp("write_report")(self.get(key), path)

    @property
    def unit_registry(self):
        """The :meth:`pint.UnitRegistry` used by the Computer."""
        return pint.get_application_registry()

    # For .compat.pyam

    def convert_pyam(
        self,
        quantities,
        year_time_dim,
        tag="iamc",
        drop: Union[set, str] = "auto",
        collapse=None,
        unit=None,
        replace_vars=None,
    ):
        """Add conversion of one or more **quantities** to IAMC format.

        Parameters
        ----------
        quantities : str or Key or list of (str, Key)
            Quantities to transform to :mod:`pyam`/IAMC format.
        year_time_dim : str
            Label of the dimension use for the ‘Year’ or ‘Time’ column of the resulting
            :class:`pyam.IamDataFrame`. The column is labelled ‘Time’ if
            ``year_time_dim=='h'``, otherwise ‘Year’.
        tag : str, optional
            Tag to append to new Keys.
        drop : iterable of str, optional
            Label of additional dimensions to drop from the resulting data frame.
            Dimensions ``h``, ``y``, ``ya``, ``yr``, and ``yv``— except for the one
            named by `year_time_dim`—are automatically dropped.
        collapse : callable, optional
            Callback to handle additional dimensions of the quantity. A
            :class:`~pandas.DataFrame` is passed as the sole argument to `collapse`,
            which must return a modified dataframe.
        unit : str or pint.Unit, optional
            Convert values to these units.
        replace_vars : str or Key
            Other reporting key containing a :class:`dict` mapping variable names to
            replace.

        Returns
        -------
        list of Key
            Each key converts a :class:`.Quantity` into a :class:`pyam.IamDataFrame`.

        See also
        --------
        compat.pyam.computations.as_pyam
        """
        self._require_compat("pyam")

        if isinstance(quantities, (str, Key)):
            quantities = [quantities]
        quantities = self.check_keys(*quantities)

        keys = []
        for qty in quantities:
            # Key for the new quantity
            qty = Key.from_str_or_key(qty)
            new_key = ":".join([qty.name, tag])

            # Prepare the computation
            comp = [
                partial(
                    # If pyam is not available, _require_compat() above will fail
                    cast(Callable, self._get_comp("as_pyam")),
                    year_time_dim=year_time_dim,
                    drop=drop,
                    collapse=collapse,
                    unit=unit,
                ),
                "scenario",
                qty,
            ]
            if replace_vars:
                comp.append(replace_vars)

            # Add and store
            self.add(new_key, tuple(comp))
            keys.append(new_key)

        return keys

    # Use convert_pyam as a helper for computations.as_pyam
    add_as_pyam = convert_pyam

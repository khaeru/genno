import json
import logging
import pickle
from functools import partial, singledispatch, update_wrapper
from hashlib import blake2b
from inspect import getmembers, iscode
from pathlib import Path
from typing import Callable, Union

from .util import unquote

log = logging.getLogger(__name__)

# Types to ignore in Encoder.default()
IGNORE = set()


@singledispatch
def _encode(o):
    # Let the base class default method raise the TypeError
    return json.JSONEncoder().default(o)


@_encode.register
def _encode_path(o: Path):
    return str(o)


class Encoder(json.JSONEncoder):
    """JSON encoder.

    This is a one-way encoder used only to serialize arguments for :func:`.hash_args`
    and :func:`.hash_code`.
    """

    @classmethod
    def ignore(cls, *types):
        """Tell the Encoder (thus :func:`.hash_args`) to ignore arguments of `types`.

        Example
        -------
        >>> class Bar:
        >>>    pass
        >>>
        >>> # Don't use Bar instances in cache keys
        >>> @genno.caching.Encoder.ignore(Bar)

        Ignore all unrecognized types

        >>> @genno.caching.Encoder.ignore(object)
        """
        IGNORE.add(types)

    @classmethod
    def register(cls, func):
        """Register a `func` to serialize a type not handled by :class:`.JSONEncoder`.

        `func` should return a type that *is* handled by JSONEncoder; see the docs.

        Example
        -------
        >>> class Foo:
        >>>    a = 3
        >>>
        >>> @genno.caching.Encoder.register
        >>> def _encode_foo(o: Foo):
        >>>     return dict(a=o.a)  # JSONEncoder can handle dict()
        """
        return _encode.register(func)

    def default(self, o):
        """For `o`, return an object serializable by the base :class:`.JSONEncoder`.

        - :class:`pathlib.Path`: the string representation of `o`.
        - :class:`code` objects (from Python's built-in :mod:`inspect` module), e.g.
          a function or lambda: :class:`blake2b` hash of the object's bytecode and its
          serialized constants.

          .. warning:: This is not 100% guaranteed to change if the operation of `o` (or
             other code called in turn by `o`) changes. If relying on this behaviour,
             check carefully.
        - Any type indicated with :meth:`.ignore`: empty :class:`tuple`.
        - Any type with a serializer registered with :meth:`.register`: the return value
          of the serializer, called on `o`.
        """

        if iscode(o):
            # Python built-in code object, from e.g. hash_code() or lambda: hash the
            # identifying information: raw bytecode & constants used
            return blake2b(
                o.co_code + json.dumps(o.co_consts, cls=self.__class__).encode()
            ).hexdigest()

        try:
            return _encode(o)
        except TypeError:
            if isinstance(o, tuple(IGNORE)):
                log.warning(f"Cache key ignores {type(o)}")
                return ()
            else:
                raise


def hash_args(*args, **kwargs):
    """Return a 20-character :class:`blake2b` hex digest of `args` and `kwargs`.

    Used by :func:`.decorate`.

    See also
    --------
    Encoder
    """
    return blake2b(
        (
            ""
            if len(args) + len(kwargs) == 0
            else json.dumps((args, kwargs), cls=Encoder)
        ).encode(),
        digest_size=20,
    ).hexdigest()


def hash_code(func: Callable) -> str:
    """Return the :class:`.blake2b` hex digest of the compiled bytecode of `func`.

    See also
    --------
    Encoder
    """
    # Get the code object
    code_obj = next(filter(lambda kv: kv[0] == "__code__", getmembers(func)))[1]
    return Encoder().default(code_obj)


def hash_contents(path: Union[Path, str], chunk_size=65536) -> str:
    """Return the :class:`.blake2b` hex digest of the contents of the file at `path`.

    Parameters
    ----------
    chunk_size : int, optional
        Read the file in chunks of this size; default 64 kB.
    """
    with Path(path).open("rb") as f:
        hash = blake2b()
        for chunk in iter(partial(f.read, chunk_size), b""):
            hash.update(chunk)
    return hash.hexdigest()


def decorate(
    func: Callable, computer=None, cache_path=None, cache_skip=False
) -> Callable:
    """Helper for :meth:`.Computer.cache`.

    Parameters
    ----------
    computer : Computer, optional
        If supplied, the ``config`` dictionary stored in the Computer is used to look
        up values for `cache_path` and `cache_skip`, at the moment when `func` is
        called.
    cache_path : os.Pathlike, optional
        Directory in which to store cache files.
    cache_skip : bool, optional
        If :obj:`True`, ignore existing cache entries and overwrite them with new
        values from `func`.

    See also
    --------
    hash_args
    hash_code
    """
    log.debug(f"Wrapping {func.__name__} in Computer.cache()")

    # Wrap the call to load_func
    def cached_load(*args, **kwargs):
        try:
            # Retrieve cache settings from the `computer`
            # Only do this at time of execution, to allow the cache_path to be adjusted
            config = unquote(computer.graph["config"])
        except AttributeError:
            # No `computer` provided; use values from arguments
            config = dict()

        _dir = config.get("cache_path", cache_path)
        _skip = config.get("cache_skip", cache_skip)

        if not _dir:
            _dir = Path.cwd()
            log.warning(f"'cache_path' configuration not set; using {_dir}")

        # Parts of the file name: function name, hash of arguments and code
        name_parts = [func.__name__, hash_args(*args, hash_code(func), **kwargs)]
        # Path to the cache file
        path = _dir.joinpath("-".join(name_parts)).with_suffix(".pkl")

        # Shorter name for logging
        short_name = f"{name_parts[0]}(<{name_parts[1][:8]}…>)"

        if not _skip and path.exists():
            log.info(f"Cache hit for {short_name}")
            with open(path, "rb") as f:
                return pickle.load(f)
        else:
            log.info(f"Cache miss for {short_name}")
            data = func(*args, **kwargs)

            with open(path, "wb") as f:
                pickle.dump(data, f)

            return data

    # Update the wrapped function with the docstring etc. of the original
    update_wrapper(cached_load, func)

    return cached_load

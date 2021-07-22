import json
import logging
import pickle
from functools import partial
from hashlib import blake2b
from inspect import getmembers
from pathlib import Path
from typing import Callable, Union

from .util import unquote

log = logging.getLogger(__name__)


class PathEncoder(json.JSONEncoder):
    """JSON encoder that handles :class:`pathlib.Path`.

    Used by :func:`.hash_args`.
    """

    def default(self, o):
        """"""
        if isinstance(o, Path):
            return str(o)
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, o)


def hash_args(*args, **kwargs):
    """Return a unique hash for `args` and `kwargs`.

    Used by :func:`.make_cache_decorator`.
    """
    if len(args) + len(kwargs) == 0:
        unique = ""
    else:
        unique = json.dumps(args, cls=PathEncoder) + json.dumps(kwargs, cls=PathEncoder)

    # Uncomment for debugging
    # log.debug(f"Cache key hashed from: {unique}")

    return blake2b(unique.encode(), digest_size=20).hexdigest()


def hash_code(func: Callable) -> str:
    """Return a :class:`.blake2b` hash of the compiled bytecode of `func`."""
    # Get the code object
    code_obj = next(filter(lambda kv: kv[0] == "__code__", getmembers(func)))[1]
    # Hash the identifying information: raw bytecode & constants used
    info = code_obj.co_code + json.dumps(code_obj.co_consts).encode()
    return blake2b(info).hexdigest()


def hash_contents(path: Union[Path, str], chunk_size=65536) -> str:
    """Return a :class:`.blake2b` hash of the contents of the file at `path`.

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


def make_cache_decorator(computer, func):
    """Helper for :meth:`.Computer.cache`."""
    log.debug(f"Wrapping {func.__name__} in Computer.cache()")

    # Wrap the call to load_func
    def cached_load(*args, **kwargs):
        # Retrieve cache settings from the Computer
        config = unquote(computer.graph["config"])
        cache_path = config.get("cache_path")
        cache_skip = config.get("cache_skip", False)

        if not cache_path:
            cache_path = Path.cwd()
            log.warning(f"'cache_path' configuration not set; using {cache_path}")

        # Parts of the file name: function name, hash of arguments and code
        name_parts = [func.__name__, hash_args(*args, hash_code(func), **kwargs)]
        # Path to the cache file
        cache_path = cache_path.joinpath("-".join(name_parts)).with_suffix(".pkl")

        # Shorter name for logging
        short_name = f"{name_parts[0]}(<{name_parts[1][:8]}…>)"

        if not cache_skip and cache_path.exists():
            log.info(f"Cache hit for {short_name}")
            with open(cache_path, "rb") as f:
                return pickle.load(f)
        else:
            log.info(f"Cache miss for {short_name}")
            data = func(*args, **kwargs)

            with open(cache_path, "wb") as f:
                pickle.dump(data, f)

            return data

    return cached_load

import json
import logging
import pickle
from hashlib import sha1
from pathlib import Path

log = logging.getLogger(__name__)


class PathEncoder(json.JSONEncoder):
    """JSON encoder that handles :class:`pathlib.Path`.

    Used by :func:`.arg_hash`.
    """

    def default(self, o):
        if isinstance(o, Path):
            return str(o)
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, o)


def arg_hash(*args, **kwargs):
    """Return a unique hash for `args` and `kwargs`.

    Used by :func:`.make_cache_decorator`.
    """
    if len(args) + len(kwargs) == 0:
        unique = ""
    else:
        unique = json.dumps(args, cls=PathEncoder) + json.dumps(kwargs, cls=PathEncoder)

    # Uncomment for debugging
    # log.debug(f"Cache key hashed from: {unique}")

    return sha1(unique.encode()).hexdigest()


def make_cache_decorator(computer, func):
    """Helper for :meth:`.Computer.cache`."""
    log.debug(f"Wrapping {func.__name__} in Computer.cache()")

    # Wrap the call to load_func
    def cached_load(*args, **kwargs):
        # Path to the cache file
        name_parts = [func.__name__, arg_hash(*args, **kwargs)]

        cache_path = computer.graph["config"].get("cache_path")

        if not cache_path:
            cache_path = Path.cwd()
            log.warning(f"'cache_path' configuration not set; using {cache_path}")

        cache_path = cache_path.joinpath("-".join(name_parts)).with_suffix(".pkl")

        # Shorter name for logging
        short_name = f"{name_parts[0]}(<{name_parts[1][:8]}…>)"

        if (
            not computer.graph["config"].get("cache_skip", False)
            and cache_path.exists()
        ):
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

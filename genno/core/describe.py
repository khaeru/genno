from collections.abc import Hashable
from functools import partial
from itertools import chain
from textwrap import shorten
from typing import Any, Mapping

import dask.core
import xarray as xr

from .key import Key

#: Default maximum length for outputs from :func:`describe_recursive`.
MAX_ITEM_LENGTH = 160


def describe_recursive(graph, comp, depth=0, seen=None):
    """Recursive helper for :meth:`.describe`.

    Parameters
    ----------
    graph :
        A dask graph.
    comp :
        A dask computation.
    depth : int
        Recursion depth. Used for indentation.
    seen : set
        Keys that have already been described. Used to avoid
        double-printing.
    """
    comp = comp if isinstance(comp, tuple) else (comp,)
    seen = set() if seen is None else seen

    indent = (" " * 2 * (depth - 1)) + ("- " if depth > 0 else "")

    # Strings for arguments
    result = []

    for arg in comp:
        # Don't fully reprint keys and their ancestors that have been seen
        if isinstance(arg, Hashable) and arg in seen:
            if depth > 0:
                # Don't print top-level items that have been seen
                result.append(f"{indent}'{arg}' (above)")
            continue
        elif isinstance(arg, (str, Key)) and arg in graph:
            # key that exists in the graph → recurse
            item = "'{}':\n{}".format(
                arg, describe_recursive(graph, graph[arg], depth + 1, seen)
            )
        elif is_list_of_keys(arg, graph):
            # list → collection of items
            item = "list of:\n{}".format(
                describe_recursive(graph, tuple(arg), depth + 1, seen)
            )
        else:
            # Anything else: use a readable string representation
            item = label(arg)

        try:
            seen.add(arg)
        except TypeError:
            pass  # `arg` is unhashable, e.g. a list
        result.append(indent + item)

    # Combine items
    return ("\n" if depth > 0 else "\n\n").join(result)


def is_list_of_keys(arg: Any, graph: Mapping) -> bool:
    """Identify a task which is a list of other keys."""
    return (
        isinstance(arg, list)
        and len(arg) > 0
        and isinstance(arg[0], Hashable)
        and arg[0] in graph
    )


def label(arg, max_length=MAX_ITEM_LENGTH) -> str:
    """Return a label for `arg`.

    The label depends on the type of `arg`:

    - :class:`.xarray.DataArray`: the first line of the string representation.
    - :func:`.partial` object: a less-verbose version that omits None arguments.
    - Item protected with :func:`.dask.core.quote`: its literal value.
    - A callable, e.g. a function: its name.
    - Anything else: its :class:`str` representation.

    In all cases, the string is no longer than `max_length`.
    """
    # Convert various types of arguments to string
    if isinstance(arg, xr.DataArray):
        # DataArray → just the first line of the string representation
        return str(arg).split("\n")[0]
    elif isinstance(arg, partial):
        # functools.partial → less verbose format
        fn_args = ", ".join(
            chain(
                map(repr, arg.args),
                filter(
                    None,
                    map(
                        lambda kw: "" if kw[1] is None else f"{kw[0]}={kw[1]}",
                        arg.keywords.items(),
                    ),
                ),
                ["..."],
            )
        )
        fn_repr = getattr(arg.func, "__name__", repr(arg.func))
        return shorten(f"{fn_repr}({fn_args})", max_length)
    elif isinstance(arg, dask.core.literal):
        # Item protected with dask.core.quote()
        return shorten(str(arg.data), max_length)
    elif callable(arg):
        if arg.__class__.__name__ == "builtin_function_or_method":
            return repr(arg).replace("function ", "")
        else:
            return getattr(arg, "__name__", str(arg))
    else:
        return shorten(str(arg), max_length)

"""Compatibility with :mod:`dask`."""


def cull(dsk, keys):
    """Like :func:`dask.optimization.cull`.

    This version calls :func:`.to_keylike` on the culled graph and dependencies to
    ensure the resulting graph does not contain :class:`.Key`.
    """
    import dask.optimization

    out0, dependencies0 = dask.optimization.cull(dsk, keys)

    # Rewrite Key to str in out0
    out1 = {to_keylike(k): to_keylike(task) for k, task in out0.items()}

    # Rewrite Key to str in dependencies0
    dependencies1 = {to_keylike(k): to_keylike(deps) for k, deps in out0.items()}

    return out1, dependencies1


def to_keylike(value):
    """Rewrite :class:`.Key` `value` (or in `value`) to :class:`.str`.

    Collections such as :class:`tuple` and :class:`list` are rewritten recursively.
    """
    from genno.core.key import Key

    if isinstance(value, (str, bytes, int, float)):
        # These are the strict types of dask.typing.Key (also tuple of same).
        # Return as-is without further checks
        return value
    elif isinstance(value, Key):
        return str(value)
    elif type(value) in (tuple, list):  # NB Only exactly these types; not subclasses
        return type(value)(map(to_keylike, value))  # Recurse; return same type
    else:
        return value

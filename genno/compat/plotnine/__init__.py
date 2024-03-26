from importlib.util import find_spec

#: :class:`bool` indicating whether :mod:`plotnine` is available.
HAS_PLOTNINE = find_spec("plotnine") is not None

if HAS_PLOTNINE:
    from .plot import Plot

    __all__ = ["Plot"]

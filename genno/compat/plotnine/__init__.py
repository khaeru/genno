try:
    import plotnine  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover
    HAS_PLOTNINE = False
else:
    HAS_PLOTNINE = True

    from .plot import Plot

    __all__ = ["Plot"]

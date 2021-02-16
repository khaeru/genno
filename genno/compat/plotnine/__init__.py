import warnings

# NB does not seem to have any effect. The entry in setup.cfg / [pytest] achieves this.
warnings.filterwarnings(
    action="ignore",
    message="Using or importing the ABCs from 'collections'",
    module="patsy",
)

try:
    import plotnine  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover
    HAS_PLOTNINE = False
else:
    HAS_PLOTNINE = True

    from .plot import Plot

    __all__ = ["Plot"]

try:
    import pyam  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover
    HAS_PYAM = False
else:
    HAS_PYAM = True

HAS_IXMP = True


def configure(path=None, **config):
    """Configure :mod:`genno` globally.

    Modifies global variables that affect the behaviour of *all* Reporters and
    computations, namely :obj:`.RENAME_DIMS`.

    Valid configuration keys—passed as *config* keyword arguments—include:

    Other Parameters
    ----------------
    rename_dims : mapping of str -> str
        Update :obj:`.RENAME_DIMS`.

    Warns
    -----
    UserWarning
        If *config* contains unrecognized keys.
    """
    from genno import core

    from .util import RENAME_DIMS

    core.configure(path, **config)

    # Dimensions to be renamed
    RENAME_DIMS.update(config.get("rename_dims", {}))

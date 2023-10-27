_warned = False


def __getattr__(name):
    global _warned
    if not _warned:
        from warnings import warn

        warn(
            f"Importing from {__name__} will be deprecated in a future version; "
            "use genno.operator instead.",
            FutureWarning,
            2,
        )
        _warned = True

    from . import operator

    return getattr(operator, name)

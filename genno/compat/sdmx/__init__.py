__all__ = [
    "codelist_to_groups",
]


def __getattr__(name: str):
    if name == "codelist_to_groups":
        from warnings import warn

        warn(
            f"Import {name} from genno.compat.sdmx; use genno.compat.sdmx.operator or "
            'Computer.require_compat("sdmx") instead',
            FutureWarning,
        )

        from . import operator

        return operator.codelist_to_groups
    else:
        raise AttributeError

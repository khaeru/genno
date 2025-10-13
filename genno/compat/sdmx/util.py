from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sdmx.format import Version
    from sdmx.model.common import (
        BaseDataSet,
        BaseDataStructureDefinition,
        BaseObservation,
        DimensionComponent,
        MaintainableArtefact,
    )


def handle_od(
    value: "str | DimensionComponent | None", structure: "BaseDataStructureDefinition"
) -> "DimensionComponent | None":
    """Handle `observation_dimension` arguments for :mod:`.sdmx.operator`.

    Ensure either None or a DimensionComponent.
    """
    import sdmx

    if isinstance(value, sdmx.model.common.DimensionComponent) or value is None:
        return value
    elif value is not None:
        return structure.dimensions.get(value)


def urn(obj: "MaintainableArtefact") -> str:
    """Return the URN of `obj`, or construct it."""
    import sdmx.urn

    if result := obj.urn:  # pragma: no cover
        return result
    else:
        return sdmx.urn.make(obj)


def handle_version(
    version: "str |Version | None",
) -> tuple["Version", type["BaseDataSet"], type["BaseObservation"]]:
    """Handle `version` arguments for :mod:`.sdmx.operator`.

    Also return either :mod:`sdmx.model.v21` or :mod:`sdmx.model.v30`, as appropriate.
    """
    import sdmx.model
    from sdmx.format import Version

    # Ensure a Version enum member
    if not isinstance(version, Version):
        version = Version[version or "2.1"]

    # Retrieve information model module
    im = {Version["2.1"]: sdmx.model.v21, Version["3.0.0"]: sdmx.model.v30}[version]

    return (
        version,
        im.get_class("StructureSpecificDataSet"),
        im.get_class("Observation"),
    )

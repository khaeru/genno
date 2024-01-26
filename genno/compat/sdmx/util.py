from typing import Optional, Tuple, Type, Union

import sdmx


def handle_od(
    value: Union[str, "sdmx.model.common.DimensionComponent", None],
    structure: "sdmx.model.common.BaseDataStructureDefinition",
) -> Optional["sdmx.model.common.DimensionComponent"]:
    """Handle `observation_dimension` arguments for :mod:`.sdmx.operator`.

    Ensure either None or a DimensionComponent.
    """
    import sdmx

    if isinstance(value, sdmx.model.common.DimensionComponent) or value is None:
        return value
    elif value is not None:
        return structure.dimensions.get(value)


def urn(obj: "sdmx.model.common.MaintainableArtefact") -> str:
    """Return the URN of `obj`, or construct it."""
    if result := obj.urn:  # pragma: no cover
        return result
    else:
        return sdmx.urn.make(obj)


def handle_version(
    version: Union["sdmx.format.Version", str, None],
) -> Tuple[
    "sdmx.format.Version",
    Type["sdmx.model.common.BaseDataSet"],
    Type["sdmx.model.common.BaseObservation"],
]:
    """Handle `version` arguments for :mod:`.sdmx.operator`.

    Also return either :mod:`sdmx.model.v21` or :mod:`sdmx.model.v30`, as appropriate.
    """
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

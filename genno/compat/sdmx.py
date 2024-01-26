from typing import Dict, Iterable, List, Mapping, Optional, Union

from genno import Quantity

try:
    import sdmx
except ModuleNotFoundError:  # pragma: no cover
    HAS_SDMX = False
else:
    HAS_SDMX = True


__all__ = [
    "codelist_to_groups",
    "dataset_to_quantity",
    "quantity_to_dataset",
]


def codelist_to_groups(
    codes: Union["sdmx.model.common.Codelist", Iterable["sdmx.model.common.Code"]],
    dim: Optional[str] = None,
) -> Mapping[str, Mapping[str, List[str]]]:
    """Convert `codes` into a mapping from parent items to their children.

    The returned value is suitable for use with :func:`~.operator.aggregate`.

    Parameters
    ----------
    codes
        Either a :class:`sdmx.Codelist <sdmx.model.common.Codelist>` object or any
        iterable of :class:`sdmx.Code <sdmx.model.common.Code>`.
    dim : str, optional
        Dimension to aggregate. If `codes` is a code list and `dim` is not given, the
        ID of the code list is used; otherwise `dim` must be supplied.
    """
    from sdmx.model.common import Codelist

    if isinstance(codes, Codelist):
        items: Iterable["sdmx.model.common.Code"] = codes.items.values()
        dim = dim or codes.id
    else:
        items = codes

    if dim is None:
        raise ValueError("Must provide a dimension ID for aggregation")

    groups = dict()
    for code in filter(lambda c: len(c.child), items):
        groups[code.id] = list(map(str, code.child))

    return {dim: groups}


def _urn(obj: "sdmx.model.common.MaintainableArtefact") -> str:
    if result := obj.urn:
        return result
    else:
        return sdmx.urn.make(obj)


def dataset_to_quantity(ds: "sdmx.model.common.BaseDataSet") -> Quantity:
    """Convert :class:`DataSet <sdmx.model.common.BaseDataSet>` to :class:`.Quantity.

    Returns
    -------
    Quantity
        The quantity may have the attributes:

        - "dataflow_urn": :attr:`urn <sdmx.model.common.MaintainableArtefact.urn>` of
          the :class:`Dataflow` referenced by the :attr:`described_by
          <sdmx.model.common.DataSet.described_by>` attribute of `ds`, if any.
        - "structure_urn": :attr:`urn <sdmx.model.common.MaintainableArtefact.urn>` of
          the :class:`DataStructureDefinition
          <sdmx.model.common.BaseDataStructureDefinition>` referenced by the
          :attr:`structured_by <sdmx.model.common.DataSet.structured_by>` attribute of
          `ds`, if any.
    """
    # Assemble attributes
    attrs: Dict[str, str] = {}
    if ds.described_by:
        attrs.update(dataflow_urn=_urn(ds.described_by))
    if ds.structured_by:
        attrs.update(structure_urn=_urn(ds.structured_by))

    return Quantity(sdmx.to_pandas(ds), attrs=attrs)


def quantity_to_dataset(
    qty: Quantity, structure: "sdmx.model.v21.DataStructureDefinition"
) -> "sdmx.model.v21.Dataset":
    """Convert :class:`.Quantity to :class:`DataSet <sdmx.model.common.BaseDataSet>`.

    The resulting data set is structure-specific and flat (not grouped into Series).
    """
    try:
        # URN of DSD stored on `qty` matches `structure`
        assert qty.attrs["structure_urn"] == _urn(structure)
    except KeyError:
        pass  # No such attribute

    # Dimensions; should be equivalent to the IDs of structure.dimensions
    dims = qty.dims

    # Create data set
    ds = sdmx.model.v21.StructureSpecificDataSet(structured_by=structure)
    m = structure.measures[0]

    def as_obs(key, value):
        """Convert a single pd.Series element to an sdmx Observation."""
        # Convert `key` tuple to an sdmx Key
        key = structure.make_key(sdmx.model.v21.Key, dict(zip(dims, key)))
        return sdmx.model.v21.Observation(dimension=key, value_for=m, value=value)

    # - Convert `qty` to pd.Series.
    # - Convert each item to an sdmx Observation.
    # - Add to `ds`.
    ds.obs.extend(as_obs(key, value) for key, value in qty.to_series().items())

    return ds


def quantity_to_message(
    qty: Quantity, structure: "sdmx.model.v21.DataStructureDefinition", **kwargs
) -> "sdmx.message.DataMessage":
    """Convert :class:`.Quantity to :class:`DataMessage <sdmx.message.DataMessage>`."""
    dm = sdmx.message.DataMessage(**kwargs)
    dm.data.append(quantity_to_dataset(qty, structure))
    return dm

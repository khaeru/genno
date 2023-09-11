from typing import TYPE_CHECKING, Iterable, List, Mapping, Optional, Union

if TYPE_CHECKING:
    from sdmx.model.common import Code, Codelist


def codelist_to_groups(
    codes: Union["Codelist", Iterable["Code"]], dim: Optional[str] = None
) -> Mapping[str, Mapping[str, List[str]]]:
    """Convert `codes` into a mapping from parent items to their children.

    The returned value is suitable for use with :func:`~.computations.aggregate`.

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
        items: Iterable["Code"] = codes.items.values()
        dim = dim or codes.id
    else:
        items = codes

    if dim is None:
        raise ValueError("Must provide a dimension ID for aggregation")

    groups = dict()
    for code in filter(lambda c: len(c.child), items):
        groups[code.id] = list(map(str, code.child))

    return {dim: groups}

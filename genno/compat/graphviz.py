import re
from os import PathLike
from typing import Mapping, MutableMapping, Optional, Set, Union

import graphviz
from dask.core import get_dependencies, ishashable, istask
from dask.dot import graphviz_to_file, name

from genno.core.describe import is_list_of_keys, label


def key_label(key):
    return unwrap(str(key))


_UNWRAP_EXPR = re.compile("^<(.*)>$")


def unwrap(label: str) -> str:
    """Unwrap any number of paired '<' and '>' at the start/end of `label`.

    These characters cause errors in graphviz/dot.
    """
    while True:
        result = _UNWRAP_EXPR.sub(r"\1", label)
        if result == label:
            return result
        else:
            label = result


def visualize(
    dsk: Mapping,
    filename: Optional[Union[str, PathLike]] = None,
    format: Optional[str] = None,
    data_attributes: Optional[Mapping] = None,
    function_attributes: Optional[Mapping] = None,
    graph_attr: Optional[Mapping] = None,
    node_attr: Optional[Mapping] = None,
    edge_attr: Optional[Mapping] = None,
    collapse_outputs=False,
    **kwargs,
):
    """Generate a Graphviz visualization of `dsk`.

    This is merged and extended version of :func:`dask.base.visualize`,
    :func:`dask.dot.dot_graph`, and :func:`dask.dot.to_graphviz` that produces output
    that is informative for genno graphs.

    Parameters
    ----------
    dsk :
        The graph to display.
    filename : Path or str, optional
        The name of the file to write to disk. If the file name does not have a suffix,
        ".png" is used by default. If `filename` is :data:`None`, no file is written,
        and dask communicates with :program:`dot` using only pipes.
    format : {'png', 'pdf', 'dot', 'svg', 'jpeg', 'jpg'}, optional
        Format in which to write output file, if not given by the suffix of `filename`.
        Default "png".
    data_attributes :
        Graphviz attributes to apply to single nodes representing keys, in addition to
        `node_attr`.
    function_attributes :
        Graphviz attributes to apply to single nodes representing operations or
        functions, in addition to `node_attr`.
    graph_attr :
        Mapping of (attribute, value) pairs for the graph. Passed directly to
        :class:`.graphviz.Digraph`.
    node_attr :
        Mapping of (attribute, value) pairs set for all nodes. Passed directly to
        :class:`.graphviz.Digraph`.
    edge_attr :
        Mapping of (attribute, value) pairs set for all edges. Passed directly to
        :class:`.graphviz.Digraph`.
    collapse_outputs : bool, optional
        Omit nodes for keys that are the output of intermediate calculations.
    kwargs :
        All other keyword arguments are added to `graph_attr`.

    Examples
    --------

    .. _visualize-example:

    Prepare a computer:

    >>> from genno import Computer
    >>> from genno.testing import add_test_data
    >>> c = Computer()
    >>> add_test_data(c)
    >>> c.add_product("z", "x:t", "x:y")
    >>> c.add("y::0", itemgetter(0), "y")
    >>> c.add("y0", "y::0")
    >>> c.add("index_to", "z::indexed", "z:y", "y::0")
    >>> c.add_single("all", ["z::indexed", "t", "config", "x:t"])

    Visualize its contents:

    >>> c.visualize("example.svg")

    This produces the output:

    .. image:: _static/visualize.svg
       :alt: Example output from graphviz.visualize.

    See also
    --------
    .describe.label
    """
    # Handle arguments
    item_attr = {
        "data": data_attributes or {},
        "func": function_attributes or {},
    }
    _graph_attr: MutableMapping = dict(graph_attr) if graph_attr else {}
    _node_attr: MutableMapping = dict(node_attr) if node_attr else {}
    edge_attr = edge_attr or {}

    # Default attributes
    _graph_attr.setdefault("rankdir", "BT")
    _node_attr.setdefault("fontname", "helvetica")

    # Assume unused kwargs are for graph_attr
    _graph_attr.update(kwargs)

    # Use a directional shape like [> in LR mode; otherwise a box
    key_shape = "cds" if _graph_attr["rankdir"] == "LR" else "box"

    g = graphviz.Digraph(
        graph_attr=_graph_attr, node_attr=_node_attr, edge_attr=edge_attr
    )

    seen = set()  # Nodes or edges already seen
    connected: Set[str] = set()  # Nodes already connected to the graph

    # Shorthand
    def _attrs(kind, key, **defaults):
        """Prepare a copy from `item_attr` for `kind` with `defaults`."""
        result = item_attr[kind].get(key, {}).copy()
        for k, v in defaults.items():
            result.setdefault(k, v)
        return result

    def _edge(a, b):
        """Add an edge to `g` and update `connected`."""
        g.edge(a, b)
        connected.update(a, b)

    # Iterate over keys, tasks in the graph
    for k, v in dsk.items():
        # A unique "name" for the node within `g`; similar to hash(k).
        k_name = name(k)

        if istask(v):
            # A task

            # Node name for the operation
            func_name = name((k, "function")) if not collapse_outputs else k_name

            # Add a node for the operation
            if collapse_outputs or func_name not in seen:
                seen.add(func_name)
                attrs = _attrs(
                    "func", k, label=unwrap(label(v[0], max_length=50)), shape=key_shape
                )
                g.node(func_name, **attrs)

            # Add an edge between the operation-node and the key-node of its output
            if not collapse_outputs:
                _edge(func_name, k_name)

            # Add edges between the operation-node and the key-nodes for each of its
            # inputs
            for dep in get_dependencies(dsk, k):
                dep_name = name(dep)
                if dep_name not in seen:
                    seen.add(dep_name)
                    attrs = _attrs("data", dep, label=key_label(dep), shape="ellipse")
                    g.node(dep_name, **attrs)
                _edge(dep_name, func_name)

        elif ishashable(v) and v in dsk:
            # Simple alias of k → v
            _edge(name(v), k_name)

        elif is_list_of_keys(v, dsk):
            # k is a list of multiple keys (genno extension)
            for _v in v:
                _edge(name(_v), k_name)

        if (not collapse_outputs or k_name in connected) and k_name not in seen:
            # Something else that hasn't been seen: add a node that may never be
            # connected
            seen.add(k_name)
            attrs = _attrs("data", k, label=key_label(k), shape="ellipse")
            g.node(k_name, **attrs)

    return graphviz_to_file(g, None if filename is None else str(filename), format)

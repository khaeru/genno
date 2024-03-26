import re
from os import PathLike
from typing import Literal, Mapping, Optional, Set, Union

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


class Visualizer:
    """Handle arguments for :func:`.visualize`."""

    def __init__(
        self,
        data_attributes: Mapping,
        function_attributes: Mapping,
        graph_attr: Mapping,
        node_attr: Mapping,
        edge_attr: Mapping,
        kwargs: Mapping,
    ):
        from graphviz import Digraph

        # Handle arguments
        self.da = data_attributes
        self.fa = function_attributes

        # Store for reference below
        self.ga = dict(graph_attr)
        self.ga.setdefault("rankdir", "BT")
        self.ga.update(kwargs)

        na = dict(node_attr)
        na.setdefault("fontname", "helvetica")

        # Create the graph and tracking collections
        self.graph = Digraph(graph_attr=self.ga, node_attr=na, edge_attr=edge_attr)

        # Nodes or edges already seen
        self.seen: Set[str] = set()
        # Nodes already connected to the graph
        self.connected: Set[str] = set()

    def get_attrs(self, kind: Literal["data", "func"], name: str, **defaults) -> dict:
        """Prepare attributes for a node of `kind`.

        If `name` is in self.da or self.fa, use those values, filling with `defaults`;
        otherwise, attributes are empty except for `defaults`."""
        if kind == "data":
            result = self.da.get(name, {}).copy()
            result.setdefault("shape", "ellipse")
        else:
            result = self.fa.get(name, {}).copy()
            # Use a directional shape like [> in LR mode; otherwise a box
            result.setdefault("shape", "cds" if self.ga["rankdir"] == "LR" else "box")

        [result.setdefault(k, v) for k, v in defaults.items()]

        return result

    def add_edge(self, a, b) -> None:
        """Add an edge to the graph."""
        self.graph.edge(a, b)
        # Update the connected nodes
        self.connected.update((a, b))

    def add_node(self, kind: Literal["data", "func"], name: str, k, v=None) -> None:
        """Add a data node to the graph."""
        if name in self.seen:
            return
        self.seen.add(name)
        _label = key_label(k) if kind == "data" else unwrap(label(v[0], max_length=50))
        self.graph.node(name, **self.get_attrs(kind, k, label=_label))

    def process(self, dsk: Mapping, collapse_outputs: bool):
        """Process the dask graph `dsk`."""
        from dask.core import get_dependencies, ishashable, istask
        from dask.dot import name

        # Iterate over keys, tasks in the graph
        for k, v in dsk.items():
            # A unique "name" for the node within `g`; similar to hash(k).
            k_name = name(k)

            if istask(v):  # A task
                # Node name for the operation, possibly distinct from its output
                func_name = name((k, "function")) if not collapse_outputs else k_name

                # Add a node for the operation
                self.add_node("func", func_name, k, v)

                # Add an edge between the operation-node and the key-node of its output
                if not collapse_outputs:
                    self.add_edge(func_name, k_name)

                # Add edges between the operation-node and the key-nodes for each of its
                # inputs
                for dep in get_dependencies(dsk, k):
                    dep_name = name(dep)
                    self.add_node("data", dep_name, dep)
                    self.add_edge(dep_name, func_name)
            elif ishashable(v) and v in dsk:  # Simple alias of k → v
                self.add_edge(name(v), k_name)
            elif is_list_of_keys(v, dsk):  # k = list of multiple keys (genno extension)
                for _v in v:
                    self.add_edge(name(_v), k_name)

            if not collapse_outputs or k_name in self.connected:
                # Something else that hasn't been seen: add a node that may never be
                # connected
                self.add_node("data", k_name, k)

        return self.graph


def visualize(
    dsk: Mapping,
    filename: Optional[Union[str, PathLike]] = None,
    format: Optional[str] = None,
    data_attributes: Optional[Mapping] = None,
    function_attributes: Optional[Mapping] = None,
    graph_attr: Optional[Mapping] = None,
    node_attr: Optional[Mapping] = None,
    edge_attr: Optional[Mapping] = None,
    collapse_outputs: bool = False,
    **kwargs,
):
    """Generate a Graphviz visualization of `dsk`.

    This is merged and extended version of :func:`dask.base.visualize`,
    :func:`dask.dot.dot_graph`, and :func:`dask.dot.to_graphviz` that produces
    informative output for genno graphs.

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
    from dask.dot import graphviz_to_file

    # Handle arguments
    v = Visualizer(
        data_attributes or {},
        function_attributes or {},
        graph_attr or {},
        node_attr or {},
        edge_attr or {},
        kwargs,
    )

    # Process the graph
    graph = v.process(dsk, collapse_outputs)

    return graphviz_to_file(graph, None if filename is None else str(filename), format)

import graphviz
from dask.core import get_dependencies, ishashable, istask
from dask.dot import box_label, graphviz_to_file, name
from dask.utils import key_split


def visualize(
    dsk,
    filename,
    format=None,
    data_attributes=None,
    function_attributes=None,
    rankdir="BT",
    graph_attr=None,
    node_attr=None,
    edge_attr=None,
    collapse_outputs=False,
    verbose=False,
    **kwargs,
):
    data_attributes = data_attributes or {}
    function_attributes = function_attributes or {}
    graph_attr = graph_attr or {}
    node_attr = node_attr or {}
    edge_attr = edge_attr or {}

    graph_attr.setdefault("rankdir", rankdir)
    node_attr.setdefault("fontname", "helvetica")

    graph_attr.update(kwargs)

    g = graphviz.Digraph(
        graph_attr=graph_attr, node_attr=node_attr, edge_attr=edge_attr
    )

    seen = set()
    connected = set()

    for k, v in dsk.items():
        k_name = name(k)
        if istask(v):
            func_name = name((k, "function")) if not collapse_outputs else k_name
            if collapse_outputs or func_name not in seen:
                seen.add(func_name)
                attrs = function_attributes.get(k, {}).copy()
                attrs.setdefault("label", key_split(k))
                attrs.setdefault("shape", "circle")
                # print(f"g.node({func_name=}, **{attrs=})")
                g.node(func_name, **attrs)
            if not collapse_outputs:
                # print(f"g.node({func_name=}, {k_name=})")
                g.edge(func_name, k_name)
                connected.add(func_name)
                connected.add(k_name)

            for dep in get_dependencies(dsk, k):
                dep_name = name(dep)
                if dep_name not in seen:
                    seen.add(dep_name)
                    attrs = data_attributes.get(dep, {}).copy()
                    attrs.setdefault("label", box_label(dep, verbose))
                    attrs.setdefault("shape", "box")
                    # print(f"g.node({dep_name=}, **{attrs=})")
                    g.node(dep_name, **attrs)
                # print(f"g.edge({dep_name=}, {func_name=})")
                g.edge(dep_name, func_name)
                connected.add(dep_name)
                connected.add(func_name)

        elif ishashable(v) and v in dsk:
            v_name = name(v)
            # print(f"g.edge({v_name=}, {k_name=})")
            g.edge(v_name, k_name)
            connected.add(v_name)
            connected.add(k_name)

        if (not collapse_outputs or k_name in connected) and k_name not in seen:
            seen.add(k_name)
            attrs = data_attributes.get(k, {}).copy()
            attrs.setdefault("label", box_label(k, verbose))
            attrs.setdefault("shape", "box")
            # print(f"g.node({k_name=}, **{attrs=})")
            g.node(k_name, **attrs)

    return graphviz_to_file(g, filename, format)

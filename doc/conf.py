# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import re

from docutils.nodes import Text
from sphinx.addnodes import pending_xref
from sphinx.ext.intersphinx import missing_reference

# -- Project information ---------------------------------------------------------------

project = "genno"
copyright = "2018–2024, Genno contributors"
author = "Genno contributors"


# -- General configuration -------------------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be extensions coming
# with Sphinx (named 'sphinx.ext.*') or your custom ones.
extensions = [
    "IPython.sphinxext.ipython_directive",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.extlinks",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "sphinx.ext.todo",
    "sphinx.ext.viewcode",
]

# List of patterns, relative to source directory, that match files and directories to
# ignore when looking for source files. This pattern also affects html_static_path and
# html_extra_path.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

nitpicky = True

rst_prolog = """
.. role:: py(code)
   :language: python
"""

# Paths that contain templates, relative to the current directory.
templates_path = ["_templates"]


def setup(app):
    """Sphinx build setup."""
    # Modify the sphinx.ext.autodoc config to handle Operators as functions
    from sphinx.ext.autodoc import FunctionDocumenter

    from genno.core.operator import Operator

    class OperatorDocumenter(FunctionDocumenter):
        @classmethod
        def can_document_member(cls, member, membername, isattr, parent) -> bool:
            return isinstance(member, Operator) or super().can_document_member(
                member, membername, isattr, parent
            )

    app.add_autodocumenter(OperatorDocumenter, override=True)

    # Connect reftarget_alias event handlers
    app.connect("doctree-read", resolve_internal_aliases)
    app.connect("missing-reference", resolve_intersphinx_aliases)


# -- Options for HTML output -----------------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for a list of
# builtin themes.
html_theme = "sphinx_book_theme"

html_theme_options = dict(
    navigation_with_keys=False,  # Silence a warning
    path_to_docs="doc",
    repository_url="https://github.com/khaeru/genno",
    show_navbar_depth=2,
    use_edit_page_button=True,
    use_issues_button=True,
    use_repository_button=True,
    use_source_button=True,
)

# -- Options for sphinx.ext.extlinks ---------------------------------------------------

extlinks = {
    "issue": ("https://github.com/khaeru/genno/issues/%s", "#%s"),
    "pull": ("https://github.com/khaeru/genno/pull/%s", "PR #%s"),
    "gh-user": ("https://github.com/%s", "@%s"),
}
extlinks_detect_hardcoded_links = False

# -- Options for sphinx.ext.intersphinx ------------------------------------------------

intersphinx_mapping = {
    "dask": ("https://docs.dask.org/en/stable", None),
    "ixmp": ("https://docs.messageix.org/projects/ixmp/en/latest", None),
    "joblib": ("https://joblib.readthedocs.io/en/latest", None),
    "graphviz": ("https://graphviz.readthedocs.io/en/stable", None),
    "matplotlib": ("https://matplotlib.org/stable", None),
    "message_ix": ("https://docs.messageix.org/en/latest", None),
    "message-ix-models": ("https://docs.messageix.org/projects/models/en/latest", None),
    "nbclient": ("https://nbclient.readthedocs.io/en/latest", None),
    "nbformat": ("https://nbformat.readthedocs.io/en/latest", None),
    "numpy": ("https://numpy.org/doc/stable", None),
    "pandas": ("https://pandas.pydata.org/docs", None),
    "pint": ("https://pint.readthedocs.io/en/stable", None),
    "platformdirs": ("https://platformdirs.readthedocs.io/en/latest", None),
    "plotnine": ("https://plotnine.org", None),
    "pyam": ("https://pyam-iamc.readthedocs.io/en/stable", None),
    "python": ("https://docs.python.org/3", None),
    "pytest": ("https://docs.pytest.org/en/stable", None),
    "sdmx1": ("https://sdmx1.readthedocs.io/en/stable", None),
    "sparse": ("https://sparse.pydata.org/en/stable", None),
    "xarray": ("https://docs.xarray.dev/en/stable", None),
}

# -- Options for sphinx.ext.napoleon ---------------------------------------------------

napoleon_preprocess_types = True
napoleon_type_aliases = {
    # Standard library
    "callable": "typing.Callable",
    "collection": "collections.abc.Collection",
    "hashable": "collections.abc.Hashable",
    "iterable": "collections.abc.Iterable",
    "mapping": "collections.abc.Mapping",
    "sequence": "collections.abc.Sequence",
    "Path": "pathlib.Path",
    # This package
    "KeyLike": "genno.core.key.KeyLike",
    # Others
    "Code": "sdmx.model.common.Code",
}

# -- Options for sphinx.ext.todo -------------------------------------------------------

todo_include_todos = True

# -- Other configuration ---------------------------------------------------------------

# Mapping from (expression) → (replacement, optional new text, optional new reftype).
# Order matters here; earlier entries are matched first.
#
# h/t https://stackoverflow.com/a/62301461
reftarget_alias = {
    r"Quantity\.units": ("genno.core.base.UnitsMixIn.units", None, None),
    "Quantity": ("genno.core.attrseries.AttrSeries", None, None),
    "AnyQuantity": ("genno.core.quantity.AnyQuantity", None, "data"),
    # Many projects' inventories lack a py:module target for the top-level module.
    # Rewrite these so that, for instance, :py:mod:`dask` becomes :std:doc:`dask`.
    "dask$": ("dask:index", None, "std:doc"),
    "pint$": ("pint:index", "pint", "std:doc"),
    "plotnine$": ("plotnine.ggplot", None, "class"),
    "pyam$": ("pyam:index", None, "std:doc"),
}


def _apply_reftarget_alias(node):
    """Apply `reftarget_alias` to `node`."""
    try:
        # Retrieve the "reftarget" attribute of the node
        target = node["reftarget"]

        # Identify an alias expression matching `reftarget`
        expr = next(filter(lambda e: re.match(e, target), reftarget_alias))
    except (KeyError, StopIteration):
        # No such attribute, or no matching expression → nothing to do
        return False

    # Unpack information about the replacement
    replacement, new_text, new_reftype = reftarget_alias[expr]

    # Resolve the ref by substituting `replacement`
    node["reftarget"] = re.sub(expr, replacement, target)

    # Rewrite the rendered text
    if new_text:
        # Find the text node child
        text_node = next(iter(node.traverse(lambda n: n.tagname == "#text")))
        # Remove the old text node, add new text node with custom text
        text_node.parent.replace(text_node, Text(new_text, ""))

    # Rewrite the reftype
    if new_reftype:
        # Maybe split "foo:bar" to ref domain "foo" and ref type "bar"
        *new_refdomain, new_reftype = new_reftype.split(":")
        node["reftype"] = new_reftype
        if new_refdomain:
            node["refdomain"] = new_refdomain[0]

    return True


def resolve_internal_aliases(app, doctree):
    """Handler for 'doctree-read' events."""
    for node in doctree.traverse(condition=pending_xref):
        _apply_reftarget_alias(node)


def resolve_intersphinx_aliases(app, env, node, contnode):
    """Handler for 'missing-reference' (intersphinx) events."""
    if _apply_reftarget_alias(node):
        # Delegate the rest of the work to intersphinx
        return missing_reference(app, env, node, contnode)

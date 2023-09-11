# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information ---------------------------------------------------------------

project = "genno"
copyright = "2018–2023, Genno contributors"
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

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and directories to
# ignore when looking for source files. This pattern also affects html_static_path and
# html_extra_path.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]


rst_prolog = """
.. role:: py(code)
   :language: python
"""


def setup(app):
    """Modify the sphinx.ext.autodoc config to handle Operators as functions."""
    from sphinx.ext.autodoc import FunctionDocumenter

    from genno.core.operator import Operator

    class OperatorDocumenter(FunctionDocumenter):
        # priority = FunctionDocumenter.priority - 1

        @classmethod
        def can_document_member(cls, member, membername, isattr, parent) -> bool:
            return isinstance(member, Operator) or super().can_document_member(
                member, membername, isattr, parent
            )

    app.add_autodocumenter(OperatorDocumenter, override=True)


# -- Options for HTML output -----------------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for a list of
# builtin themes.
html_theme = "sphinx_book_theme"

html_theme_options = dict(
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
    "dask": ("https://docs.dask.org/en/stable/", None),
    "ixmp": ("https://docs.messageix.org/projects/ixmp/en/latest", None),
    "joblib": ("https://joblib.readthedocs.io/en/latest/", None),
    "graphviz": ("https://graphviz.readthedocs.io/en/stable/", None),
    "message_ix": ("https://docs.messageix.org/en/latest", None),
    "pandas": ("https://pandas.pydata.org/docs/", None),
    "pint": ("https://pint.readthedocs.io/en/stable/", None),
    "plotnine": ("https://plotnine.readthedocs.io/en/stable/", None),
    "pyam": ("https://pyam-iamc.readthedocs.io/en/stable/", None),
    "python": ("https://docs.python.org/3/", None),
    "sdmx1": ("https://sdmx1.readthedocs.io/en/stable", None),
    "xarray": ("https://docs.xarray.dev/en/stable/", None),
}

# -- Options for sphinx.ext.todo -------------------------------------------------------

todo_include_todos = True

# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information ---------------------------------------------------------------

project = "genno"
copyright = "2018–%Y, Genno contributors"
author = "Genno contributors"


# -- General configuration -------------------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be extensions coming
# with Sphinx (named 'sphinx.ext.*') or your custom ones.
extensions = [
    # First-party
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.extlinks",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "sphinx.ext.todo",
    "sphinx.ext.viewcode",
    # Others
    "genno.compat.sphinx.autodoc_operator",
    "genno.compat.sphinx.rewrite_refs",
    "IPython.sphinxext.ipython_directive",
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

# -- Options for HTML output -----------------------------------------------------------

html_css_files = ["custom.css"]

html_logo = "_static/hammer-duotone.svg"

html_static_path = ["_static"]

html_theme = "furo"

GH_URL = "https://github.com/khaeru/genno"
html_theme_options = dict(
    footer_icons=[
        {
            "name": "GitHub",
            "url": GH_URL,
            "html": """
                <svg stroke="currentColor" fill="currentColor" stroke-width="0" viewBox="0 0 16 16">
                    <path fill-rule="evenodd" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8z"></path>
                </svg>
            """,
            "class": "",
        },
    ],
    top_of_page_buttons=["view", "edit"],
    source_repository=GH_URL,
    source_branch="main",
    source_directory="doc/",
)

html_title = "genno"

# -- Options for genno.compat.sphinx.reference_alias -----------------------------------

# Mapping from expression → replacement.
# Order matters here; earlier entries are matched first.
reference_aliases = {
    r"Quantity\.units": "genno.core.base.UnitsMixIn.units",
    "Quantity": "genno.core.attrseries.AttrSeries",
    "AnyQuantity": ":data:`genno.core.quantity.AnyQuantity`",
    #
    # Many projects (including Sphinx itself!) do not have a py:module target in for the
    # top-level module in objects.inv. Resolve these using :doc:`index` or similar for
    # each project.
    "dask$": ":std:doc:`dask:index`",
    "pint$": ":std:doc:`pint <pint:index>`",
    "plotnine$": ":class:`plotnine.ggplot`",
    "pyarrow$": ":std:doc:`pyarrow <pyarrow:python/index>`",
    "pyam$": ":std:doc:`pyam:index`",
    "sphinx$": ":std:doc:`sphinx <sphinx:index>`",
}

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
    "pyarrow": ("https://arrow.apache.org/docs", None),
    "python": ("https://docs.python.org/3", None),
    "pytest": ("https://docs.pytest.org/en/stable", None),
    "sdmx1": ("https://sdmx1.readthedocs.io/en/stable", None),
    "sparse": ("https://sparse.pydata.org/en/stable", None),
    "sphinx": ("https://www.sphinx-doc.org/en/master", None),
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

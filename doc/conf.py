# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information ---------------------------------------------------------------

project = "genno"
copyright = "2018–2024, Genno contributors"
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

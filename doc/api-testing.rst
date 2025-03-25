Test and documentation utilities
********************************

.. autodata:: genno.core.computer.DEFAULT_WARN_ON_RESULT_TUPLE

:mod:`genno.testing`
====================

.. automodule:: genno.testing
   :members:

.. automodule:: genno.testing.jupyter
   :members:

.. currentmodule:: genno.compat.sphinx

Sphinx extensions
=================

.. automodule:: genno.compat.sphinx

Document instances of :class:`.Operator`
----------------------------------------

.. automodule:: genno.compat.sphinx.autodoc_operator
   :members:

Rewrite Sphinx references
-------------------------

To use this extension, add a setting :py:`reference_aliases` in :file:`conf.py` with content like the following:

.. code-block:: python

   # Mapping from expression → replacement.
   # Order matters here; earlier entries are matched first.
   reference_aliases = {
       r"Quantity\.units": "genno.core.base.UnitsMixIn.units",
       "KeyLike": ":data:`genno.core.key.KeyLike`",
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

In this dictionary, the **keys** are regular expressions matching part or all of the target of a Sphinx reference.
The **values** are replacement content *or* entire references; using the latter, it is possible to transmute references from one category to another.
For example, in:

.. code-block:: python

   from genno.types import AnyQuantity

   def myfunc(q: "AnyQuantity") -> None: ...

…the string type annotation :py:`q: "AnyQuantity"` is automatically converted by Sphinx to ``:py:class:`AnyQuantity```.
This will *always* fail, because :obj:`.AnyQuantity` is a TypeAlias, not a class.
The :py:`reference_aliases` entry above replaces this auto-generated reference with one that resolves correctly.

See also the comments in the example above about projects whose :file:`objects.inv` lacks a target for the module itself.

.. automodule:: genno.compat.sphinx.rewrite_refs
   :members:

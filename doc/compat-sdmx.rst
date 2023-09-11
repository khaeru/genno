SDMX (:mod:`.compat.sdmx`)
**************************

:doc:`Package documentation <sdmx1:index>`

Note that this package is available in PyPI as ``sdmx1``.
To install the correct package, use:

.. code-block:: sh

   pip install genno[sdmx]

To ensure the function is available:

.. code-block:: python

   c = Computer()
   c.require_compat("genno.compat.sdmx")
   c.add(..., "codelist_to_groups", ...)

.. currentmodule:: genno.compat.sdmx

.. automodule:: genno.compat.sdmx
   :members:

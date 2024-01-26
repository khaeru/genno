.. currentmodule:: genno.compat.sdmx

SDMX (:mod:`.compat.sdmx`)
**************************

:doc:`Package documentation <sdmx1:index>`

.. automodule:: genno.compat.sdmx

Note that this package is available in PyPI as ``sdmx1``.
To install the correct package, use:

.. code-block:: sh

   pip install genno[sdmx]

To ensure the operators are available:

.. code-block:: python

   c = Computer()
   c.require_compat("sdmx")
   c.add(..., "codelist_to_groups", ...)

.. automodule:: genno.compat.sdmx.operator
   :members:

   .. autosummary::

      codelist_to_groups
      dataset_to_quantity
      quantity_to_dataset
      quantity_to_message

   This module also registers an implementation of :func:`.write_report` that handles :class:`sdmx.message.DataMessage` objects, such as those produced by :func:`.quantity_to_message`.

:mod:`ixmp`
***********

:doc:`Package documentation <ixmp:index>`

.. currentmodule:: genno.compat.ixmp

.. automodule:: genno.compat.ixmp
   :members:
   :exclude-members: rename_dims

.. automodule:: genno.compat.ixmp.computations
   :members:

.. automodule:: genno.compat.ixmp.reporter
   :members:

.. automodule:: genno.compat.ixmp.util
   :members:

.. _config-ixmp:

Configuration
=============

:mod:`.compat.ixmp` adds a ``rename_dims:`` configuration file section.

.. automethod:: genno.compat.ixmp.rename_dims

Computer-specific configuration.

Affects data loaded from a :class:`ixmp.Scenario` using :func:`data_for_quantity`.
Native dimension names are mapped; in the example below, the dimension "i" is present in the :class:`.Computer` as "i_renamed" on all Quantities/Keys in which it appears.

.. code-block:: yaml

    rename_dims:
      i: i_renamed

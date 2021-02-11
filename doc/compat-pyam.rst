Pyam (:mod:`.compat.pyam`)
**************************

:doc:`Package documentation <pyam:index>`

.. currentmodule:: genno.compat.pyam

.. automodule:: genno.compat.pyam
   :members:
   :exclude-members: iamc

.. automodule:: genno.compat.pyam.computations
   :members:

.. automodule:: genno.compat.pyam.util
   :members:

.. _config-pyam:

Configuration
=============

:mod:`.compat.pyam` adds a ``iamc:`` configuration file section.

.. automethod:: genno.compat.pyam.iamc

Computer-specific configuration.

Invokes :meth:`.Computer.convert_pyam` (plus extra computations) to reformat data from :class:`.Quantity` into a :class:`pyam.IamDataFrame` data structure.
Each entry contains:

``variable:`` (:class:`str`)
   Variable name.
   This is used two ways: it is placed in 'Variable' column of the resulting IamDataFrame; and the reporting key to :meth:`~.Computer.get` the data frame is ``<variable>:iamc``.
``base:`` (:class:`str`)
   Key for the quantity to convert.
``select:`` (:class:`dict`, optional)
   Keyword arguments to :func:`.computations.select`.
``rename:`` (:class:`dict`, optional)
   Passed to :meth:`convert_pyam`.
``replace:`` (:class:`dict`, optional)
   Passed to :meth:`.convert_pyam`.
``drop:`` (:class:`list` of :class:`str`, optional)
   Dimensions to drop (→ convert_pyam).
``unit:`` (:class:`str`, optional)
   Force output in these units (→ convert_pyam).

Additional entries are passed as keyword arguments to :func:`.collapse`, which is then given as the `collapse` callback for :meth:`.convert_pyam`.

:func:`.collapse` formats the 'Variable' column of the IamDataFrame.
The variable name replacements from the ``iamc variable names:`` section of the config file are applied to all variables.

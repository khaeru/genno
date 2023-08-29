Pyam (:mod:`.compat.pyam`)
**************************

:doc:`Package documentation <pyam:index>`

.. currentmodule:: genno.compat.pyam

.. automodule:: genno.compat.pyam
   :members:
   :exclude-members: iamc

   The :doc:`“IAMC data structure” <pyam:data>` is a particular data structure with either 6 or 7 dimensions: ``model``, ``scenario``, ``region``, ``variable``, ``unit``, either ``year`` or ``time``, and optionally ``subannual``.
   Data with this structure are usually stored in a tablular “IAMC format,” wherein each dimension is stored as one column, and the remaining column, labeled ``value``, contains observation values.

   Using :func:`.add_as_pyam` (:py:`Computer.add(..., "as_pyam", ...)`):

   - ``model`` and ``scenario`` are populated from the attributes of the object returned by the Computer key ``scenario``;
   - ``variable`` contains the name(s) of each of the `quantities`, or others constructed by `collapse` (see below);
   - ``unit`` contains the units associated with each of the `quantities`; and
   - ``year``, ``time``, and optionally ``subannual`` can be created using `rename` or `collapse` operations.

   A callback function (`collapse`) can be supplied that modifies the data before it is converted to an :class:`~pyam.IamDataFrame`; for instance, to concatenate extra dimensions into ``variable`` labels.
   Other dimensions can simply be dropped (with `drop`).
   Dimensions that are not collapsed or dropped will appear as additional columns in the resulting :class:`~pyam.IamDataFrame`; this is valid, but non-standard data per the IAMC format.

   For example, here the labels for the MESSAGEix ``t`` (technology) and ``m`` (mode) dimensions are appended to a fixed string to construct ``variable`` labels:

   .. code-block:: python

      c = Computer

      def m_t(df):
         """Collapse `t` and `m` dimensions to an IAMC 'Variable' string."""
         df["variable"] = "Activity|" + df["t"] + "|" + df["m"]
         return df

      ACT = c.full_key('ACT')
      keys = c.add(ACT, "as_pyam", "ya", collapse=m_t, drop=["t", "m"])


.. automodule:: genno.compat.pyam.computations
   :members:

   .. autosummary::

      as_pyam
      add_as_pyam
      concat
      write_report

   .. .. autofunction:: as_pyam

   .. autofunction:: add_as_pyam

.. _config-pyam:

Configuration
=============

:mod:`.compat.pyam` adds a handler for a ``iamc:`` configuration file section.

.. automethod:: genno.compat.pyam.iamc

   Computer-specific configuration.

   Invokes :func:`.add_as_pyam` and adds additional computations to convert data from :class:`.Quantity` to a :class:`pyam.IamDataFrame`.
   Each entry contains:

   ``variable:`` (:class:`str`)
      Variable name.
      This is used two ways: it is placed in the ``variable`` label of the resulting IamDataFrame; and the Computer key for executing the conversion is ``<variable>:iamc``.
   ``base:`` (:class:`str`)
      Key for the quantity to convert.
   ``select:`` (:class:`dict`, optional)
      Keyword arguments to :func:`.computations.select`.
      This selection is performed while data is in :class:`.Quantity` format, before it is passed to :func:`.as_pyam`.
   ``rename:`` (:class:`dict`, optional)
      Passed to :func:`.as_pyam`.
   ``replace:`` (:class:`dict`, optional)
      Passed to :func:`.as_pyam`.
   ``drop:`` (:class:`list` of :class:`str`, optional)
      Passed to :func:`.as_pyam`.
   ``unit:`` (:class:`str`, optional)
      Passed to :func:`.as_pyam`.

   Any further additional entries are passed as keyword arguments to :func:`.collapse`, which is then given as the `collapse` callback for :func:`.as_pyam`.

   :func:`.collapse` formats the ``variable`` labels of the IamDataFrame.
   The variable name replacements from the ``iamc variable names:`` section of the config file are applied to all variables.

Utilities
=========

.. currentmodule:: genno.compat.pyam.util

.. automodule:: genno.compat.pyam.util
   :members:

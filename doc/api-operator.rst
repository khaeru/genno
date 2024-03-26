Operators
*********

.. automodule:: genno.operator
   :members:

   Unless otherwise specified, these functions accept and return :class:`.Quantity` objects for data arguments/return values.
   The names and signatures of many operators match the corresponding methods on the :class:`.Quantity` class, and thus also the :class:`.xarray.DataArray` methods of the same names.

   Genno's :ref:`compatibility modules <compat>` each provide additional operators.

   Numerical operators:

   .. autosummary::
      add
      aggregate
      broadcast_map
      clip
      combine
      disaggregate_shares
      div
      group_sum
      index_to
      interpolate
      mul
      pow
      product
      ratio
      round
      sub
      sum
      add_sum
      where

   Data manipulation and transformation:

   .. autosummary::
      apply_units
      as_quantity
      assign_units
      concat
      convert_units
      drop_vars
      relabel
      rename
      rename_dims
      select
      unique_units_from_dim

   Input and output:

   .. autosummary::
      load_file
      add_load_file
      write_report

Helper functions for adding tasks to Computers
----------------------------------------------

.. autofunction:: add_binop
.. autofunction:: add_load_file
.. autofunction:: add_sum

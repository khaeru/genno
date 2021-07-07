API reference
*************

.. currentmodule:: genno

.. contents::
   :local:
   :depth: 3

Top-level classes and functions
===============================

.. autosummary::

   configure
   Computer
   Key
   Quantity

.. autofunction:: configure
   :noindex:

.. autoclass:: genno.Computer
   :members:
   :exclude-members: add, add_as_pyam, add_load_file, apply, cache, convert_pyam, graph

   A Computer is used to describe (:meth:`add` and related methods) and then execute (:meth:`get` and related methods) **tasks** stored in a :attr:`graph`.
   Advanced users may manipulate the graph directly; but common reporting tasks can be handled by using Computer methods.

   Instance attributes:

   .. autosummary::
      default_key
      graph
      keys
      modules
      unit_registry

   General-purpose methods for describing tasks and preparing computations:

   .. autosummary::
      add
      add_queue
      add_single
      apply
      cache
      describe
      visualize

   Helper methods to simplify adding specific computations:

   .. autosummary::
      add_file
      add_product
      aggregate
      convert_pyam
      disaggregate

   Exectuing tasks:

   .. autosummary::
      get
      write

   Utility and configuration methods:

   .. autosummary::
      check_keys
      configure
      full_key
      get_comp
      infer_keys
      require_compat

   .. autoattribute:: graph

      Dictionary keys are either :class:`.Key`, :class:`str`, or any other hashable value.

      Dictionary values are *computations*, one of:

      1. Any other, existing key in the Computer. This functions as an alias.
      2. Any other literal value or constant, to be returned directly.
      3. A *task* :class:`tuple`: a callable (e.g. function), followed by zero
         or more computations, e.g. keys for other tasks.
      4. A :class:`list` containing zero or more of (1), (2), and/or (3).

      :mod:`genno` reserves some keys for special usage:

      ``"config"``
         A :class:`dict` storing configuration settings.
         See :doc:`config`.
         Because this information is stored *in* the :attr:`graph`, it can be
         used as one input to other computations.

      Some inputs to tasks may be confused for (1) or (4), above.
      The recommended way to protect these is:

      - Literal :class:`str` inputs to tasks: use :func:`functools.partial` on the function that is the first element of the task tuple.

      - :class:`list` of :class:`str`: use :func:`dask.core.quote` to wrap the list.

   .. automethod:: add

      The `data` argument may be:

      :class:`list`
         A list of computations, like ``[(list(args1), dict(kwargs1)), (list(args2), dict(kwargs2)), ...]`` → passed to :meth:`add_queue`.

      :class:`str` naming a computation
         e.g. "select", retrievable with :meth:`get_comp`.
         :meth:`add_single` is called with ``(key=args[0], data, *args[1], **kwargs``, i.e. applying the named computation. to the other parameters.

      :class:`str` naming another Computer method
         e.g. :meth:`add_file` → the named method is called with the `args` and `kwargs`.

      :class:`.Key` or other :class:`str`:
         Passed to :meth:`add_single`.

      :meth:`add` may be used to:

      - Provide an alias from one *key* to another:

        >>> from genno import Computer
        >>> rep = Computer()  # Create a new Computer object
        >>> rep.add('aliased name', 'original name')

      - Define an arbitrarily complex computation in a Python function that
        operates directly on the :class:`ixmp.Scenario`:

        >>> def my_report(scenario):
        >>>     # many lines of code
        >>>     return 'foo'
        >>> rep.add('my report', (my_report, 'scenario'))
        >>> rep.finalize(scenario)
        >>> rep.get('my report')
        foo

   .. automethod:: apply

      The `generator` may have a type annotation for Computer on its first positional argument.
      In this case, a reference to the Computer is supplied, and `generator` can use the Computer methods to add many keys and computations:

      .. code-block:: python

         def my_gen0(c: genno.Computer, **kwargs):
             c.load_file("file0.txt", **kwargs)
             c.load_file("file1.txt", **kwargs)

         # Use the generator to add several computations
         rep.apply(my_gen0, units="kg")

      Or, `generator` may ``yield`` a sequence (0 or more) of (`key`, `computation`), which are added to the :attr:`graph`:

      .. code-block:: python

         def my_gen1(**kwargs):
             op = partial(computations.load_file, **kwargs)
             yield from (f"file:{i}", (op, "file{i}.txt")) for i in range(2)

         rep.apply(my_gen1, units="kg")

   .. automethod:: cache

      Use this function to decorate another function to be added as the computation/callable in a task:

      .. code-block:: python

         c = Computer(cache_path=Path("/some/directory"))

         @c.cache
         def myfunction(*args, **kwargs):
             # Expensive operations, e.g. loading large files
             return data

         c.add("myvar", (myfunction,))

         # Data is cached in /some/directory/myfunction-*.pkl

      On the first call of :meth:`get` that invokes `func`, the data requested is returned, but also cached in the cache directory (see :ref:`Configuration → Caching <config-cache>`).

      On subsequent calls, if the cache exists, it is used instead of calling the (possibly slow) `func`.

      If the ``"cache_skip"`` configuration option is :obj:`True`, `func` is always called.

   .. automethod:: convert_pyam

      The :doc:`IAMC data format <pyam:data>` includes columns named 'Model', 'Scenario', 'Region', 'Variable', 'Unit'; one of 'Year' or 'Time'; and 'value'.

      Using :meth:`convert_pyam`:

      - 'Model' and 'Scenario' are populated from the attributes of the object returned by the Reporter key ``scenario``;
      - 'Variable' contains the name(s) of the `quantities`;
      - 'Unit' contains the units associated with the `quantities`; and
      - 'Year' or 'Time' is created according to `year_time_dim`.

      A callback function (`collapse`) can be supplied that modifies the data before it is converted to an :class:`~pyam.IamDataFrame`; for instance, to concatenate extra dimensions into the 'Variable' column.
      Other dimensions can simply be dropped (with `drop`).
      Dimensions that are not collapsed or dropped will appear as additional columns in the resulting :class:`~pyam.IamDataFrame`; this is valid, but non-standard IAMC data.

      For example, here the values for the MESSAGEix ``technology`` and ``mode`` dimensions are appended to the 'Variable' column:

      .. code-block:: python

          def m_t(df):
              """Callback for collapsing ACT columns."""
              # .pop() removes the named column from the returned row
              df['variable'] = 'Activity|' + df['t'] + '|' + df['m']
              return df

          ACT = rep.full_key('ACT')
          keys = rep.convert_pyam(ACT, 'ya', collapse=m_t, drop=['t', 'm'])




.. autoclass:: genno.Key
   :members:

   Quantities are indexed by 0 or more dimensions.
   A Key refers to a quantity using three components:

   1. a string :attr:`name`,
   2. zero or more ordered :attr:`dims`, and
   3. an optional :attr:`tag`.

   For example, for a :math:`\text{foo}` with with three dimensions :math:`a, b, c`:

   .. math:: \text{foo}^{abc}

   Key allows a specific, explicit reference to various forms of “foo”:

   - in its full resolution, i.e. indexed by a, b, and c:

     >>> k1 = Key("foo", ["a", "b", "c"])
     >>> k1
     <foo:a-b-c>

   - in a partial sum over one dimension, e.g. summed across dimension c, with  remaining dimensions a and b:

     >>> k2 = k1.drop('c')
     >>> k2 == 'foo:a-b'
     True

   - in a partial sum over multiple dimensions, etc.:

     >>> k1.drop('a', 'c') == k2.drop('a') == 'foo:b'
     True

   - after it has been manipulated by other computations, e.g.

     >>> k3 = k1.add_tag('normalized')
     >>> k3
     <foo:a-b-c:normalized>
     >>> k4 = k3.add_tag('rescaled')
     >>> k4
     <foo:a-b-c:normalized+rescaled>

   **Notes:**

   A Key has the same hash, and compares equal to its :class:`str` representation.
   A Key also compares equal to another key or :class:`str` with the same dimensions in any other order.
   ``repr(key)`` prints the Key in angle brackets ('<>') to signify that it is a Key object.

   >>> str(k1)
   'foo:a-b-c'
   >>> repr(k1)
   '<foo:a-b-c>'
   >>> hash(k1) == hash("foo:a-b-c")
   True
   >>> k1 == "foo:c-b-a"
   True

   Keys are **immutable**: the properties :attr:`name`, :attr:`dims`, and :attr:`tag` are *read-only*, and the methods :meth:`append`, :meth:`drop`, and :meth:`add_tag` return *new* Key objects.

   Keys may be generated concisely by defining a convenience method:

   >>> def foo(dims):
   >>>     return Key('foo', dims.split())
   >>> foo('a b c')
   <foo:a-b-c>


.. autoclass:: genno.Quantity
   :members:

The :class:`.Quantity` constructor converts its arguments to an internal, :class:`xarray.DataArray`-like data format:

.. code-block:: python

   # Existing data
   data = pd.Series(...)

   # Convert to a Quantity for use in reporting calculations
   qty = Quantity(data, name="Quantity name", units="kg")
   rep.add("new_qty", qty)

Common :mod:`genno` usage, e.g. in :mod:`message_ix`, creates large, sparse data frames (billions of possible elements, but <1% populated); :class:`~xarray.DataArray`'s default, 'dense' storage format would be too large for available memory.

- Currently, Quantity is :class:`.AttrSeries`, a wrapped :class:`pandas.Series` that behaves like a :class:`~xarray.DataArray`.
- In the future, :mod:`genno` will use :class:`.SparseDataArray`, and eventually :class:`~xarray.DataArray` backed by sparse data, directly.

The goal is that all :mod:`genno`-based code, including built-in and user computations, can treat quantity arguments as if they were :class:`~xarray.DataArray`.


Computations
============

.. automodule:: genno.computations
   :members:

   Unless otherwise specified, these methods accept and return :class:`.Quantity` objects for data arguments/return values.

   Genno's :ref:`compatibility modules <compat>` each provide additional computations.

   Calculations:

   .. autosummary::
      add
      aggregate
      apply_units
      broadcast_map
      combine
      disaggregate_shares
      group_sum
      pow
      product
      ratio
      select
      sum

   Input and output:

   .. autosummary::
      load_file
      write_report

   Data manipulation:

   .. autosummary::
      concat


Internal format for quantities
==============================

.. currentmodule:: genno.core.quantity

.. automodule:: genno.core.quantity
   :members: assert_quantity

.. currentmodule:: genno.core.attrseries

.. automodule:: genno.core.attrseries
   :members:

.. currentmodule:: genno.core.sparsedataarray

.. automodule:: genno.core.sparsedataarray
   :members: SparseDataArray, SparseAccessor


Utilities
=========

.. automodule:: genno.util
   :members:

.. automodule:: genno.caching
   :members:

API reference
*************

.. currentmodule:: genno

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
   :exclude-members: add, add_queue, apply, eval, graph

   A Computer is used to prepare (:meth:`add` and related methods) and then execute (:meth:`get` and related methods) **computations** stored in a :attr:`graph`.
   Advanced users may manipulate the graph directly; but most computations can be prepared can be handled by using Computer methods.

   Instance attributes:

   .. autosummary::
      default_key
      graph
      keys
      modules
      unit_registry

   General-purpose methods for preparing computations and tasks:

   .. autosummary::
      add
      add_queue
      add_single
      aggregate
      apply
      cache
      describe
      eval
      visualize

   Executing computations:

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

   Deprecated:

   .. autosummary::
      add_file
      add_product
      convert_pyam
      disaggregate

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
         Because this information is stored *in* the :attr:`graph`, it can be used as one input to other computations.

      Some inputs to tasks may be confused for (1) or (4), above.
      The recommended way to protect these is:

      - Literal :class:`str` inputs to tasks: use :func:`functools.partial` on the function that is the first element of the task tuple.

      - :class:`list` of :class:`str`: use :func:`dask.core.quote` to wrap the list.

   .. automethod:: add

      The `data` argument may be:

      :class:`list`
         A list of computations, like :py:`[(list(args1), dict(kwargs1)), (list(args2), dict(kwargs2)), ...]` → passed to :meth:`add_queue`.

      :class:`str` naming an operator
         e.g. "select", retrievable with :meth:`get_comp`.
         :meth:`add_single` is called with :py:`(key=args[0], data, *args[1], **kwargs)`, that is, applying the named operator to the other parameters.

      :class:`.Key` or other :class:`str`:
         Passed to :meth:`add_single`.

      :meth:`add` may be used to:

      - Provide an alias from one *key* to another:

        >>> from genno import Computer
        >>> rep = Computer()  # Create a new Computer object
        >>> rep.add('aliased name', 'original name')

      - Define an arbitrarily complex operator in a Python function that operates directly on the :class:`ixmp.Scenario`:

        >>> def my_report(scenario):
        >>>     # many lines of code
        >>>     return 'foo'
        >>> rep.add('my report', (my_report, 'scenario'))
        >>> rep.finalize(scenario)
        >>> rep.get('my report')
        foo

   .. automethod:: add_queue

      This method allows to add many computations at once by, in effect, calling :meth:`add` repeatedly with sets of positional and (optionally) keyword arguments taken from the `queue`.
      The argument may be:

      - A prepared/static data structure, like a :class:`list`, where each item is either a 2-:class:`tuple` of :py:`(args, kwargs)` or only a tuple of :py:`args` that can be passed to :meth:`add`.
      - A generator that yields items of the same type(s).

      Given this initial sequence of items, :meth:`add_queue` will…

      - Pass each item in turn to :meth:`add`;
      - If an item fails to be added—for instance, with :class:`MissingKeyError` on one of its inputs—and `max_tries` > 1: re-append that item to the queue so that it can be attempted again;
      - If an item fails to be added at least `max_tries` times: take an action according to `fail`.

      This behaviour makes :meth:`add_queue` tolerant of entries in `queue` that are out-of-order: individual items may fail in calls to :meth:`add` on initial passes through the queue, but eventually succeed once their inputs are available.

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

   .. automethod:: eval

      .. rubric:: Examples

      Parse a multi-line string and add tasks to compute z, a, b, d, and e.
      The dimensions of each are automatically inferred given the dimension of the existing operand, x.

      .. code-block:: python

         >>> c = Computer()
         >>> # (Here, add tasks to compute a quantity like "x:t-y")
         >>> added = c.eval(
         ...     """
         ...     z = - (0.5 / (x ** 3))
         ...     a = x ** 3 + z
         ...     b = a + a
         ...     d = assign_units(b, "km")
         ...     e = index_to(d, dim="t", label="foo1")
         ...     """
         ... )
         >>> added[-1]
         <e:t-y>

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

   - in a partial sum over one dimension, e.g. summed across dimension c, with remaining dimensions a and b:

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

The goal is that all :mod:`genno`-based code, including built-in and user functions, can treat quantity arguments as if they were :class:`~xarray.DataArray`.

.. automodule:: genno
   :members: MissingKeyError

Operators
=========

.. automodule:: genno.computations
   :members:

   Unless otherwise specified, these functions accept and return :class:`.Quantity` objects for data arguments/return values.

   Genno's :ref:`compatibility modules <compat>` each provide additional operators.

   Numerical operators:

   .. autosummary::
      add
      aggregate
      broadcast_map
      combine
      disaggregate_shares
      div
      group_sum
      index_to
      interpolate
      mul
      add_mul
      pow
      product
      ratio
      sub
      sum
      add_sum

   Input and output:

   .. autosummary::
      load_file
      add_load_file
      write_report

   Data manipulation:

   .. autosummary::
      apply_units
      assign_units
      concat
      convert_units
      relabel
      rename_dims
      select

Helper functions for adding tasks to Computers
----------------------------------------------

.. autofunction:: add_load_file
.. autofunction:: add_mul


Internal format for quantities
==============================

.. currentmodule:: genno.core.quantity

.. automodule:: genno.core.quantity
   :members: CLASS, assert_quantity, maybe_densify

.. currentmodule:: genno.core.attrseries

.. automodule:: genno.core.attrseries
   :members:
   :exclude-members: AttrSeries

.. autoclass:: AttrSeries
   :members:

   .. py:attribute:: name

      The name of this Quantity.

      Like :attr:`.xarray.DataArray.name`.

.. currentmodule:: genno.core.sparsedataarray

.. automodule:: genno.core.sparsedataarray
   :members: SparseDataArray, SparseAccessor

.. currentmodule:: genno.compat.xarray

.. autoclass:: DataArrayLike


Internals and utilities
=======================

.. automodule:: genno.compat.graphviz
   :members:

.. automodule:: genno.core.describe
   :members:

.. automodule:: genno.core.graph
   :members:

.. automodule:: genno.core.key
   :members: KeyLike, iter_keys, single_key

.. automodule:: genno.core.operator
   :members:

.. automodule:: genno.util
   :members:

Utilities for testing
=====================

.. automodule:: genno.testing
   :members:
   :exclude-members: parametrize_quantity_class

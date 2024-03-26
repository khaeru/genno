.. currentmodule:: genno

Top-level classes and functions
*******************************

.. autosummary::

   Computer
   Key
   KeySeq
   Quantity
   assert_quantity
   configure
   get_class
   set_class

Also:
:class:`.ComputationError`,
:class:`.KeyExistsError`,
:class:`.MissingKeyError`,
:class:`.Operator`,
:func:`.literal`,
:func:`.quote`.

.. autoclass:: genno.Computer
   :members:
   :exclude-members: add, add_queue, apply, eval, graph

   A Computer is used to prepare (:meth:`add` and related methods) and then execute (:meth:`get` and related methods) **computations** stored in a :attr:`graph`.
   Advanced users may manipulate the graph directly; but most computations can be prepared using the methods of Computer.

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
      get_operator
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
      3. A *task* :class:`tuple`: a callable (such as a function or any object with a :meth:`~object.__call__` method), followed by zero or more keys (referring to the output of other computations), or computations directly.
      4. A :class:`list` containing zero or more of (1), (2), and/or (3).

      :mod:`genno` reserves some keys for special usage:

      ``"config"``
         A :class:`dict` storing configuration settings.
         See :doc:`config`.
         Because this information is stored *in* the :attr:`graph`, it can be used as one input to other operators.

      Some inputs to tasks may be confused for (1) or (4), above.
      The recommended way to protect these is:

      - Literal :class:`str` inputs to tasks: use :func:`functools.partial` on the function that is the first element of the task tuple.

      - :class:`list` of :class:`str`: use :func:`dask.core.quote` to wrap the list.

   .. automethod:: add

      The `data` argument may be:

      :class:`list`
         A list of computations, like :py:`[(list(args1), dict(kwargs1)), (list(args2), dict(kwargs2)), ...]` → passed to :meth:`add_queue`.

      :class:`str` naming an operator
         e.g. "select", retrievable with :meth:`get_operator`.
         :meth:`add_single` is called with :py:`(key=args[0], data, *args[1], **kwargs)`, that is, applying the named operator to the other parameters.

      :class:`.Key` or other :class:`str`:
         Passed to :meth:`add_single`.

      :meth:`add` may be used to:

      - Provide an alias from one *key* to another:

        >>> from genno import Computer
        >>> c = Computer()  # Create a new Computer object
        >>> c.add('aliased name', 'original name')

      - Define an arbitrarily complex operator in a Python function that operates directly on the :class:`ixmp.Scenario`:

        >>> def my_func(scenario):
        >>>     # many lines of code
        >>>     return 'foo'
        >>> c.add('my report', my_func, 'scenario')
        >>> c.finalize(scenario)
        >>> c.get('my report')
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
         c.apply(my_gen0, units="kg")

      Or, `generator` may ``yield`` a sequence (0 or more) of (`key`, `computation`), which are added to the :attr:`graph`:

      .. code-block:: python

         def my_gen1(**kwargs):
             op = partial(operator.load_file, **kwargs)
             yield from (f"file:{i}", (op, "file{i}.txt")) for i in range(2)

         c.apply(my_gen1, units="kg")

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
   :py:`repr(key)` prints the Key in angle brackets ('<>') to signify that it is a Key object.

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

   .. _key-arithmethic:

   Keys can also be manipulated using some of the Python arithmetic operators:

   - :py:`+`: and :py:`-`: manipulate :attr:`.tag`, same as :meth:`.add_tag` and :meth:`.remove_tag` respectively:

     >>> k1 = Key("foo", "abc", "bar+baz+qux")
     >>> k1
     <foo:a-b-c:bar+baz+qux>
     >>> k2 + "newtag"
     <foo:a-b-c:bar+baz+qux+newtag>
     >>> k1 - "baz"
     <foo:a-b-c:bar+qux>
     >>> k1 - ("bar", "baz")
     <foo:a-b-c:qux>

   - :py:`*` and :py:`/`: manipulate :attr:`dims`, similar to :meth:`.append`/:attr:`.product` and :attr:`.drop`, respectively:

     >>> k1 * "d"
     <foo:a-b-c-d>
     >>> k1 * ("e", "f")
     <foo:a-b-c-e-f>
     >>> k1 * Key("bar", "ghi")
     <foo:a-b-c-g-h-i>

     >>> k1 / "a"
     <foo:b-c>
     >>> k1 / ("a", "c")
     <foo:b>
     >>> k1 / Key("baz", "cde")
     <foo:a-b>

.. autoclass:: genno.KeySeq
   :members:

   When preparing chains or complicated graphs of computations, it can be useful to use a sequence or set of similar keys to refer to the intermediate steps.
   The :class:`.KeySeq` class is provided for this purpose.
   It supports several ways to create related keys starting from a *base key*:

   >>> ks = KeySeq("foo:x-y-z:bar")

   One may:

   - Use item access syntax:

     >>> ks["a"]
     <foo:x-y-z:bar+a>
     >>> ks["b"]
     <foo:x-y-z:bar+b>

   - Use the Python built-in :func:`.next`.
     This always returns the next key in a sequence of integers, starting with :py:`0` and continuing from the *highest previously created Key*:

     >>> next(ks)
     <foo:x-y-z:bar+0>

     # Skip some values
     >>> ks[5]
     <foo:x-y-z:bar+5>

     # next() continues from the highest
     >>> next(ks)
     <foo:x-y-z:bar+6>

   - Treat the KeySeq as callable, optionally with any value that has a :class:`.str` representation:

     >>> ks("c")
     <foo:x-y-z:bar+c>

     # Same as next()
     >>> ks()
     <foo:x-y-z:bar+7>

   - Access the most recently generated item:

     >>> ks.prev
     <foo:x-y-z:bar+7>

   - Access the base Key or its properties:

     >>> ks.base
     <foo:x-y-z:bar>
     >>> ks.name
     "foo"

   - Access a :class:`dict` of all previously-created keys.
     Because :class:`dict` is order-preserving, the order of keys and values reflects the order in which they were created:

     >>> tuple(ks.keys)
     ("a", "b", 0, 5, 6, "a", 7)

   The same Python arithmetic operators usable with Key are usable with KeySeq; they return a new KeySeq with a different :attr:`~.KeySeq.base`:

   >>> ks * "w"
   <KeySeq from 'foo:x-y-z-w:bar'>
   >>> ks / ("x", "z")
   <KeySeq from 'foo:z:bar'>

.. autoclass:: Quantity

The :class:`.Quantity` constructor converts its arguments to an internal, :class:`xarray.DataArray`-like data format:

.. code-block:: python

   # Existing data
   data = pd.Series(...)

   # Convert to a Quantity for use in genno calculations
   qty = Quantity(data, name="Quantity name", units="kg")
   c.add("new_qty", qty)

Common :mod:`genno` usage, e.g. in :mod:`message_ix`, creates large, sparse data frames (billions of possible elements, but <1% populated); :class:`~xarray.DataArray`'s default, 'dense' storage format would be too large for available memory.

- Currently, Quantity implemented as is :class:`.AttrSeries`, a wrapped :class:`pandas.Series` that behaves like a :class:`~xarray.DataArray`.
- In the future, :mod:`genno` will use :class:`.SparseDataArray`, and eventually directly :class:`~xarray.DataArray` backed by sparse data.

The goal is that all :mod:`genno`-based code, including built-in and user functions, can treat quantity arguments as if they were :class:`~xarray.DataArray`.

Quantity has a :attr:`~.Quantity.units` attribute, which can be set using either :class:`str` or :class:`pint.Unit`.

Quantity supports the standard binary operations with unit-aware behaviour:
:meth:`~.object.__add__`,
:meth:`~.object.__radd__`,
:meth:`~.object.__mul__`,
:meth:`~.object.__rmul__`,
:meth:`~.object.__pow__`,
:meth:`~.object.__rpow__`,
:meth:`~.object.__sub__`,
:meth:`~.object.__radd__`,
:meth:`~.object.__truediv__`, and
:meth:`~.object.__rtruediv__`.
This means that correct units are derived from the units of operands and attached to the resulting Quantity.

Quantity has the following methods and attributes that exactly mirror the signatures and types of the corresponding :class:`.xarray.DataArray` items.

.. autosummary::
   ~genno.core.attrseries.AttrSeries.assign_coords
   ~genno.core.attrseries.AttrSeries.bfill
   ~genno.core.attrseries.AttrSeries.clip
   ~genno.core.attrseries.AttrSeries.coords
   ~genno.core.attrseries.AttrSeries.cumprod
   ~genno.core.attrseries.AttrSeries.data
   ~genno.core.attrseries.AttrSeries.dims
   ~genno.core.attrseries.AttrSeries.drop
   ~genno.core.attrseries.AttrSeries.drop_vars
   ~genno.core.attrseries.AttrSeries.expand_dims
   ~genno.core.attrseries.AttrSeries.ffill
   ~genno.core.attrseries.AttrSeries.interp
   ~genno.core.attrseries.AttrSeries.item
   ~genno.core.attrseries.AttrSeries.rename
   ~genno.core.attrseries.AttrSeries.sel
   ~genno.core.attrseries.AttrSeries.shape
   ~genno.core.attrseries.AttrSeries.shift
   ~genno.core.attrseries.AttrSeries.squeeze
   ~genno.core.attrseries.AttrSeries.sum
   ~genno.core.attrseries.AttrSeries.to_dataframe
   ~genno.core.attrseries.AttrSeries.to_series
   ~genno.core.attrseries.AttrSeries.transpose
   ~genno.core.attrseries.AttrSeries.where

.. autofunction:: configure
   :noindex:

.. automodule:: genno
   :members: ComputationError, KeyExistsError, MissingKeyError, Operator, assert_quantity, get_class, literal, quote, set_class

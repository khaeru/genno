What's new
**********

.. contents::
   :local:
   :backlinks: none
   :depth: 1

.. Next release
.. ============

v1.13.0 (2022-08-17)
====================

- 1-dimensional quantities are handled in :func:`.relabel` and as weights in :func:`.sum` (:pull:`68`).
- :func:`.load_file` will read a header comment like ``# Units: kg / s`` and apply the indicated units to the resulting quantity (:pull:`68`).
- :func:`.div` and :func:`.mul` become the canonical names, matching :mod:`.operator` and other parts of the Python standard library (:pull:`68`).
  :func:`.ratio` and :func:`.product` are retained as aliases, for compatibility.
- Ensure data passed to :meth:`.Plot.generate` has a "value" column; use short units format by default (:pull:`68`).

v1.12.0 (2022-07-18)
====================

- New computation :func:`.index_to` (:pull:`65`).
- :ref:`config-general` configuration items are more flexible (:pull:`65`).

  - ``comp: null`` or omitted allows to specify a simple collection of other computations.
  - A bare string ``key:`` is left as-is; only keys with (a) dimension(s) and/or tag are parsed to :class:`.Key`.

- :func:`.repr` of :class:`.Quantity` displays its units (:pull:`65`).
- Bug fix: :meth:`.Computer.convert_pyam` handles its `tag` argument correctly, generating keys like ``foo:x-y-z:iamc`` or ``bar::iamc`` when applied to existing keys like ``foo:x-y-z`` or ``bar`` (:pull:`65`).
  Previously the generated keys would be e.g. ``bar:iamc``, which incorrectly treats "iamc" as a (sole) dimension rather than a tag.
- :meth:`.Computer.require_compat` can handle arbitrary module names as strings, as well as module objects (:pull:`63`).

v1.11.0 (2022-04-20)
====================

Migration notes
---------------

The `index` keyword argument to :meth:`.Computer.add_single` / :meth:`.add` is deprecated (:pull:`60`) and will be removed in or after v3.0.0.
Indexing behaviour changes slightly: :meth:`.Computer.full_key` always returns the :class:`.Key` which matches its arguments and has the *greatest number of dimensions*.
For instance:

.. code-block:: python

    c.add_product("foo", "bar:a-b-c", "baz:x-y-z", sums=True)

…will generate a key ``<foo:a-b-c-x-y-z>`` and all partial sums over subsets of its dimensions; ``c.full_key("foo")`` will return this key.

Care should be taken to avoid adding 2+ keys with the same name, tag, **and** number of dimensions:

.. code-block:: python

   c.add("foo:a-b-c", ...)
   c.add("foo:l-m-n", ...)
   c.add("foo:x-y-z", ...)

This situation is ambiguous and the behaviour of :meth:`Computer.full_key` is undefined.
Instead, add a :attr:`~.Key.tag` to disambiguate.

All changes
-----------

- :meth:`.Key.product` accepts :class:`str` arguments (:pull:`60`).
- New class method :meth:`.Key.bare_name` (:pull:`60`).
- Infer dimensions for e.g. ``X:*:tag`` in :ref:`config-general` configuration items (:pull:`60`).
- Handle the `fail` argument to :meth:`.Computer.aggregate` through :ref:`config-aggregate` configuration items (:pull:`60`).
- New computations :func:`.relabel` and :func:`.rename_dims` (:pull:`60`).
- Improve perfomance for adding large number of computations to :class:`.Computer` (:pull:`60`).

v1.10.0 (2022-03-31)
====================

- Add :func:`.testing.assert_units` (:pull:`58`).

v1.9.2 (2022-03-03)
===================

- Silence :func:`collect_units` when units are explicitly `""`, rather than :obj:`None` (:pull:`56`).
- Add explicit implementations of :meth:`~.object.__radd__`, :meth:`~.object.__rmul__`, :meth:`~.object.__rsub__` and :meth:`~.object.__rtruediv__` for e.g. ``4.2 * Quantity(...)`` (:pull:`55`)
- Improve typing of :meth:`.Quantity.shift` (:pull:`55`)

v1.9.1 (2022-01-27)
===================

Note that installing ``genno[pyam]`` (including via ``genno[compat]``) currently forces the installation of an old version of :mod:`pint`; version 0.17 or earlier.
Users wishing to use :mod:`genno.compat.pyam` should first install ``genno[pyam]``, then ``pip install --upgrade pint`` to restore a recent version of pint (0.18 or newer) that is usable with genno.

- :func:`computations.concat` works with :class:`.AttrSeries` with misaligned dimensions (:pull:`53`).
- Improve typing of :class:`.Quantity` and :class:`.Computer` to help with using `mypy <https://mypy.readthedocs.io>`_ on code that uses :mod:`genno` (:pull:`53`).

v1.9.0 (2021-11-23)
===================

- Fix error messages raised by :meth:`.AttrSeries.sel` on incorrect usage (:pull:`52`).
- :mod:`genno` no longer supports Python 3.6 or earlier, following :mod:`xarray` (:pull:`52`).

v1.8.1 (2021-07-27)
===================

Bug fixes
---------

- :class:`.Path` not serialized correctly in :mod:`.caching` (:pull:`51`).

v1.8.0 (2021-07-27)
===================

- Improve caching (:pull:`50`):

  - Handle a lambda functions in :meth:`.cache`-decorated code.
  - Add :meth:`.Encoder.register` and :meth:`.Encoder.ignore` for downstream code to extend hashing of function arguments into cache keys.
  - Expand docs.

v1.7.0 (2021-07-22)
===================

- Add :func:`.computations.interpolate` and supporting :meth:`.AttrSeries.interp` (:pull:`48`).
  This code works around issues `pandas#25460 <https://github.com/pandas-dev/pandas/issues/25460>`_ and `pandas#31949 <https://github.com/pandas-dev/pandas/issues/31949>`_.
- :meth:`.Computer.cache` now also invalidates cache if the compiled bytecode of the decorated function changes (:pull:`48`).
- Separate and expand docs of :doc:`cache` to show how to check modification time and/or contents of files (:issue:`49`, :pull:`48`).
- Add :attr:`.Quantity.units` attribute for access to units (:pull:`48`).
- :attr:`.AttrSeries.dims` and :attr:`.AttrSeries.coords` behave like :class:`~xarray.DataArray` for 1-D quantities (:pull:`48`)

v1.6.0 (2021-07-07)
===================

- Add :meth:`Key.permute_dims` (:pull:`47`).
- Improve performance of :meth:`Computer.check_keys` (:pull:`47`).

v1.5.2 (2021-07-06)
===================

- Bug fix: order-insensitive :attr:`Key.dims` broke :meth:`~.Computer.get` in some circumstances (:pull:`46`).

v1.5.1 (2021-07-01)
===================

- Bug fix: :meth:`.infer_keys` raises :class:`AttributeError` under some circumstances (:pull:`45`).

v1.5.0 (2021-06-27)
===================

- Adjust :meth:`.test_assign_coords` for xarray 0.18.2 (:pull:`43`).
- Make :attr:`Key.dims` order-insensitive so that ``Key("foo", "ab") == Key("foo", "ba")`` (:pull:`42`); make corresponding changes to :class:`Computer` (:pull:`44`).
- Fix “:class:`AttributeError`: 'COO' object has no attribute 'item'” on :meth:`SparseDataArray.item` (:pull:`41`).

v1.4.0 (2021-04-26)
===================

- :meth:`.plotnine.Plot.save` automatically converts inputs (specified with :attr:`.Plot.inputs`) from :class:`.Quantity` to :class:`~pandas.DataFrame`, but others (e.g. basic Python types) are passed through unchanged (:pull:`40`).
- :meth:`.plotnine.Plot.save` generates no output file if :meth:`~.plotnine.Plot.generate` returns :obj:`None`/empty :class:`list`.
- Quote :class:`dict` argument to :meth:`.Computer.aggregrate` (for grouped aggregation) to avoid collisions between its contents and other graph keys.

v1.3.0 (2021-03-22)
===================

- Bump minimum version of :mod:`sparse` from 0.10 to 0.12 and adjust to changes in this version (:pull:`39`)

  - Remove :meth:`.SparseDataArray.equals`, obviated by improvements in :mod:`sparse`.

- Improve :class:`.AttrSeries` (:pull:`39`)

  - Implement :meth:`~.AttrSeries.drop_vars` and :meth:`~.AttrSeries.expand_dims`.
  - :meth:`~.AttrSeries.assign_coords` can relabel an entire dimension.
  - :meth:`~.AttrSeries.sel` can accept :class:`.DataArray` indexers and rename/combine dimensions.

v1.2.1 (2021-03-08)
===================

- Bug fix: Provide abstract :class:`.Quantity.to_series` method for type checking in packages that depend on :mod:`genno`.

v1.2.0 (2021-03-08)
===================

- :class:`.Quantity` becomes an actual class, rather than a factory function; :class:`.AttrSeries` and :class:`.SparseDataArray` are subclasses (:pull:`37`).
- :class:`.AttrSeries` gains methods :meth:`~.AttrSeries.bfill`, :meth:`~.AttrSeries.cumprod`, :meth:`~.AttrSeries.ffill`, and :meth:`~.AttrSeries.shift` (:pull:`37`)
- :func:`.computations.load_file` uses the `skipinitialspace` parameter to :func:`pandas.read_csv`; extra dimensions not mentioned in the `dims` parameter are preserved (:pull:`37`).
- :meth:`.AttrSeries.sel` accepts :class:`xarray.DataArray` for xarray-style indexing (:pull:`37`).

v1.1.1 (2021-02-22)
===================

- Bug fix: :meth:`.Computer.add_single` incorrectly calls :meth:`.check_keys` on iterables (e.g. :class:`pandas.DataFrame`) that are not computations (:pull:`36`).

v1.1.0 (2021-02-16)
===================

- :func:`.computations.add` transforms compatible units, and raises an exception for incompatible units (:pull:`31`).
- Improve handling of scalar quantities (:pull:`31`).
- :class:`~.plotnine.Plot` is fault-tolerant: if any of the input quantities are missing, it becomes a no-op (:pull:`31`).
- :meth:`.Computer.configure` accepts a `fail` argument, allowing partial handling of configuration data/files, with errors logged but not raised (:pull:`31`).
- New :func:`.computations.pow` (:pull:`31`).

v1.0.0 (2021-02-13)
===================

- Adjust for usage by :mod:`ixmp.reporting` and :mod:`message_ix.reporting` (:pull:`28`):

  - Reduce minimum Python version to 3.6.
    This is lower than the minimum version for xarray (3.7), but matches ixmp, etc.
  - Remove :mod:`compat.ixmp`; this code has been moved to :mod:`ixmp.reporting`, replacing what was there.
    Likewise, remove :mod:`compat.message_ix`.
  - Simplify the form & parsing of ``iamc:`` section entries in configuration files:

    - Remove unused feature to add :func:`group_sum` to the chain of tasks.
    - Keys now conform more closely to the arguments of :meth:`Computer.convert_pyam`.

  - Move argument-checking from :func:`.as_pyam` to :meth:`.convert_pyam()`.
  - Simplify semantics of :func:`genno.config.handles` decorator.
     Remove ``CALLBACKS`` feature, for now.
  - :meth:`Computer.get_comp` and :meth:`.require_compat` are now public methods.
  - Expand tests.

- Protect :class:`.Computer` configuration from :func:`dask.optimization.cull`; this prevents infinite recursion if the configuration contains strings matching keys in the graph. Add :func:`.unquote` (:issue:`25`, :pull:`26`).
- Simplify :func:`.collect_units` and improve unit handling in :func:`.ratio`  (:issue:`25`, :pull:`26`).
- Add file-based caching via :meth:`.Computer.cache` and :mod:`genno.caching` (:issue:`20`, :pull:`24`).

v0.4.0 and earlier
==================

v0.4.0 (2021-02-07)
-------------------

- Add file-based configuration in :mod:`genno.config` and :doc:`associated documentation <config>` (:issue:`8`, :pull:`16`).

v0.3.0 (2021-02-05)
-------------------

- Add :doc:`compat-plotnine` compatibility (:pull:`15`).
- Add a :doc:`usage` overview to the documentation (:pull:`13`).

v0.2.0 (2021-01-18)
-------------------

- Increase test coverage to 100% (:pull:`12`).
- Port code from :mod:`message_ix.reporting` (:pull:`11`).
- Add :mod:`.compat.pyam`.
- Add a `name` parameter to :func:`.load_file`.

v0.1.0 (2021-01-10)
-------------------

- Initial code port from :mod:`ixmp.reporting`.

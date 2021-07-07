What's new
**********

.. contents::
   :local:
   :backlinks: none
   :depth: 1

.. Next release
.. ============

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

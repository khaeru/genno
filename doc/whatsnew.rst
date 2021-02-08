What's new
**********

.. contents::
   :local:
   :backlinks: none
   :depth: 1

Next release
============

- Protect :class:`.Computer` configuration from :func:`dask.optimization.cull`; this prevents infinite recursion if the configuration contains strings matching keys in the graph. Add :func:`.unquote` (:issue:`25`, :pull:`26`).
- Simplify :func:`.collect_units` and improve unit handling in :func:`.ratio`  (:issue:`25`, :pull:`26`).
- Add file-based caching via :meth:`.Computer.cache` and :mod:`genno.caching` (:issue:`20`, :pull:`24`).

v0.4.0 (2021-02-07)
===================

- Add file-based configuration in :mod:`genno.config` and :doc:`associated documentation <config>` (:issue:`8`, :pull:`16`).

v0.3.0 (2021-02-05)
===================

- Add :doc:`compat-plotnine` compatibility (:pull:`15`).
- Add a :doc:`usage` overview to the documentation (:pull:`13`).

v0.2.0 (2021-01-18)
===================

- Increase test coverage to 100% (:pull:`12`).
- Port code from :mod:`message_ix.reporting` (:pull:`11`).
- Add :mod:`.compat.pyam`.
- Add a `name` parameter to :func:`.load_file`.

v0.1.0 (2021-01-10)
===================

- Initial code port from :mod:`ixmp.reporting`.

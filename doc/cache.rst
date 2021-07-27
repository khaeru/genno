Caching
*******

.. contents::
   :local:
   :backlinks: none

Basics
======

Use :meth:`.Computer.cache` to decorate another function, `func`, that will be added as the computation/callable in a task.
Caching is useful when :meth:`.get` is called multiple times on the same Computer, or across processes, invoking a slow `func` each time.

.. code-block:: python

    # Configure the directory for cache file storage
    c = Computer(cache_path=Path("/some/directory"))

    @c.cache
    def myfunction(*args, **kwargs):
        # Expensive operations, e.g. load large files;
        # invoke external programs
        return data

    c.add("myvar", (myfunction,))

    # Data is cached in /some/directory/myfunction-*.pkl
    c.get("myvar")

    # Cached value is loaded and returned
    c.get("myvar")


A cache key is computed from:

1. the name of `func`.
2. the arguments to `func`, and
3. the compiled bytecode of `func` (see :func:`hash_code`).

If a file exists in ``cache_path`` with a matching key, it is loaded and returned instead of calling `func`.

If no matching file exists (a “cache miss”) or the ``cache_skip`` configuration option is :obj:`True`, `func` is executed and its return value is cached in the cache directory, ``cache_path`` (see :ref:`Configuration → Caching <config-cache>`).
A cache miss will occur if any part of the key changes; that is, if:

1. the function is renamed in the source code,
2. the function is called with different arguments, or
3. the function source code is modified.

Cache data loaded from files
============================

Consider a function that loads a very large file, or performs some slow processing on its contents:

.. code-block:: python

    from pathlib import Path

    import pandas as pd
    from genno import Quantity

    @c.cache
    def slow_data_load(path, _extra_cache_key=None):
        # Load data in some way
        result = pd.read_xml(path, ...)
        # … further processing …
        return Quantity(result)

We want to cache the result of :func:`slow_data_load`, but have the cache refreshed when the file contents change.
We do this using the `_extra_cache_key` argument to the function.
This argument is not used in the function, but *does* affect the value of the cache key.

When calling the function, pass some value that indicates whether the contents of `path` have changed.
One possibility is the modification time, via :meth:`.Path.stat`:

.. code-block:: python

    def load_cached_1(path):
        return slow_data_load(path, path.stat().st_mtime)

Another possibility is to hash the entire file.
:func:`hash_contents` is provided for this purpose:

.. code-block:: python

    from genno.caching import hash_contents

    def load_cached_2(path):
        return slow_data_load(path, hash_contents(path))

.. warning:: For very large files, even hashing the file in this way can be slow, and this check must *always* be performed in order to check for a matching cache key.

The decorated functions can be used as computations in the graph, or called directly:

.. code-block:: python

    c.add("A1", load_cached_1, "example-file-A.xml")
    c.add("A2", load_cached_2, "example-file-A.xml")

    # Load and process the contents of example-file-A.xml
    c.get("A1")

    # Load again; the value is retrieved from cache if the
    # file has not been modified
    c.get("A1")

    # Same without using the Computer
    load_cached1("example-file-A.xml")
    load_cached1("example-file-A.xml")

Integrate and extend
====================

- :class:`.Encoder` may be configured to handle (or ignore) additional/custom types that may appear as arguments to functions decorated with :meth:`.Computer.cache`.
  See the examples for :meth:`.Encoder.register` and :meth:`.Encoder.ignore`.
- :func:`.decorate` can be used entirely independently of any :class:`.Computer` by passing the `cache_path` (and optional `cache_skip`) keyword arguments:

  .. code-block:: python

      from functools import partial

      from genno.caching import decorate

      # Create a decorator with a custom cache path
      mycache = partial(decorate, cache_path=Path("/path/to/cache"))

      @mycache
      def func(a, b=2):
          return a ** b

  In this usage, it offers a subset of the feature-set of :class:`joblib.Memory`


Internals and utilities
=======================

.. automodule:: genno.caching
   :members:

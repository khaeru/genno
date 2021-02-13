.. currentmodule:: genno.config

Configuration
*************

As shown in :ref:`Concepts and usage <describe-tasks>`, a :class:`.Computer` can be populated programmatically.
:mod:`genno` can also read a simple **configuration format** in which settings and tasks are specified.

.. contents::
   :local:
   :depth: 2
   :backlinks: none

Overview
========

Ways to configure
-----------------

Configuration is read through the :meth:`.Computer.configure` method, or the top level :func:`genno.configure` function.

Both methods accept either keyword arguments specifying the configuration values, or a `path` keyword argument that gives the path to a :file:`.json` or :file:`.yaml`-format file. For instance, the following are all equivalent:

.. code-block:: python

   # Create the computer before configuring from a JSON file
   c = Computer()
   c.configure(path="config-W.json")

   # Create and configure from a YAML file in one step
   c = Computer(path="config-W.yaml")

   # Pass a data structure to configure()
   info = dict(
     general=[
       dict(comp="product", key="W:a-b-c-d", inputs=["X::", "Y:d"], sums=True)
     ]
   )
   c = Computer()
   c.configure(**info)

   # Use the API to add a computation directly
   c = Computer()
   # add_product() infers the dimensions of W will be a-b-c-d
   c.add_product("W", "X:a-b-c-d", "Y:d", sums=True)


…with the following file contents:

.. code-block:: yaml
   :caption: config-W.yaml

   general:
   - comp: product
     key: W:a-b-c-d
     inputs: ["X::", "Y:d"]
     sums: true

.. code-block:: json
   :caption: config-W.json

   {
     "general": [
       {
         "comp": "product",
         "key": "W:a-b-c-d",
         "inputs": ["X::", "Y:d"],
         "sums": true
       }
     ]
   }

Global- and specific configuration
----------------------------------

Configuration is either **global** or **specific** to a certain Computer.
For instance, :ref:`config-units` configuration is global; it affects all Computers, and can be set using either :func:`genno.configure` or :meth:`.Computer.configure`.
On the other hand, other configuration such as :ref:`config-files` adds tasks to a specific Computer, so it can only be set using :meth:`.Computer.configure`.

.. autofunction:: genno.configure

Custom handlers
---------------

The configuration file is divided into **sections**.
Generally each section contains a list of items, and each item is itself a mapping; see the built-in sections listed below.
:mod:`.genno.config` has one **handler** function for each section, and is extensible.
For instance, the genno compatibility module for :ref:`pyam <config-pyam>` defines a handler for the section ``iamc:``; or the separate package :mod:`ixmp` defines a handler for the sections ``filters:`` and ``rename_dims:``.

The :func:`.handles` decorator can be used to mark a custom function that handles a custom configuration section:

.. code-block:: python

    from genno.config import handles

    @handles("my-section")
    def custom_handler(c: Computer, info):
        print(f"Handle {info['name']}")
        print(f"  with inputs {repr(info['inputs'])}")

        # Use a default value for one setting
        key = info.get("key", "foo")
        print(f"Output key: {key}")

        # Manipulate the Computer instance `c` in some way
        c.add("… etc.")

.. code-block:: yaml
   :caption: my-config.yaml

    # This section is handled by genno's built-in handlers
    general:
    - comp: product
       key: W:a-b-c-d
       inputs: ["X::", "Y:d"]
       sums: true

    # These items are handled by the custom handler
    my-section:
    - name: item-a
      inputs: [X, Y]
    - name: item-b
      key: bar
      inputs: [W, Z]

.. autofunction:: handles

.. autodata:: HANDLERS

.. autodata:: STORE

Specific sections
=================

``aggregate:``
--------------

.. autofunction:: aggregate

Computer-specific configuration.

Invokes :meth:`.Computer.aggregate` add tasks with :func:`.computations.aggregate` or :func:`.computations.sum`, computing sums across labels within one dimension of a quantity.
Each entry contains:

``_quantities:`` list of 0 or more keys
   Quantities to be aggregated.
   The full dimensionality of the key(s) is inferred.
``_tag:`` (:class:`str`)
   New tag to append to the keys for the aggregated quantities.
``_dim:`` (:class:`str`)
   Dimensions on which to aggregate.

Note the leading underscores.
This is to distinguish these from all other keys, which are treated as group names.
The corresponding values are lists of labels along the dimension to sum.

Example
~~~~~~~

.. code-block:: yaml

   aggregate:
   - _quantities: [foo, bar]
     _tag: aggregated
     _dim: a

     baz123: [baz1, baz2, baz3]
     baz12: [baz1, baz2]

If the full dimensionality of the input quantities are ``foo:a-b`` and ``bar:a-b-c``, then :meth:`.add_aggregate` creates the new quantities ``foo:a-b:aggregated`` and ``bar:a-b-c:aggregated``.
These new quantities have the new labels ``baz123`` and ``baz12`` along their ``a`` dimension, with sums of the indicated values.

``alias:``
----------

.. autofunction:: alias

Computer-specific configuration.

This section simply makes the output of one task available under another key.

.. code-block:: yaml

    alias:
      "foo:x-y": "bar:x-y"
      "baz:x-y": "bar:x-y"


.. _config-cache:

Caching
-------

Computer-specific configuration that controls the behaviour of functions decorated with :meth:`.Computer.cache`.

``cache_path:`` (:class:`pathlib.Path`, optional)
   Base path for cache files.
   If not provided, defaults to the current working directory.
``cache_skip:`` (:class:`bool`, optional)
   If :obj:`True`, existing cache files are never used; files with the same cache key are overwritten.


``combine:``
------------

.. autofunction:: combine

Computer-specific configuration.

Invokes :meth:`.Computer.add_combination` to add tasks with :func:`computations.combine`, computing a weighted sum of multiple Quantities.
Each item contains:

``key:``
   Key for the new quantity, including dimensionality.
``inputs:`` (:class:`list` of :class:`dict`)
   Inputs to the weighted sum.
   Each dict contains:

  ``quantity:`` (required)
     Key for the input quantity.
     :meth:`.add_combination` infers the proper dimensionality from the dimensions of `key` plus dimension to `select` on.
  ``select:`` (:class:`dict`, optional)
     Selectors to be applied to the input quantity.
     Keys are dimensions; values are either single labels, or lists of labels.
     In the latter case, the sum is taken across these values, so that the result has the same dimensionality as `key`.
  ``weight:`` (:class:`int`, optional)
     Weight for the input quantity; default 1.

Example
~~~~~~~

For the following YAML:

.. code-block:: yaml

   combine:
   - key: foo:a-b-c
     inputs:
     - quantity: bar
       weight: -1
     - quantity: baz::tag
       select: {d: [d1, d2, d3]}

…:meth:`.add_combination` infers:

.. math::

   \text{foo}_{abc} = -1 \times \text{bar}_{abc}
   + 1 \times \sum_{d \in \{ d1, d2, d3 \}}{\text{baz}_{abcd}^\text{(tag)}}
   \quad \forall \quad a, b, c

``default:`` key/task
---------------------

.. autofunction:: default

Computer-specific configuration.

This sets :attr:`.Computer.default_key`, used when :meth:`.get` is called without arguments.


.. _config-files:

``files:`` input
----------------

.. autofunction:: files

Computer-specific configuration.

Invokes :meth:`.Computer.add_file` to add :func:`.computations.load_file`.
If the ``path:`` key is a relative path, it is resolved relative to the directory that contains the configuration file, else the current working directory.

.. code-block:: yaml

    files:
    - path: ./input0.csv
      key: d_check
    # 'dims' argument can be supplied as list or dict
    - path: ./input1.csv
      key: input1-0
      dims: [i, j_dim]  # Omit extra dimension 'foo'
    - path: ./input1.csv
      key: input1-1
      dims: {i: i, j_dim: j}


``general:``
------------

.. autofunction:: general

Computer-specific configuration.

This is, as the name implies, the most generalized section.
Each item contains:

``comp:``
  Refers to the name of a computation that is available in the namespace of :mod:`genno.computations`, or custom computations registered by compatibility modules or third-party packages.
  See :meth:`Computer.add` and :meth:`Computer.get_comp`.
  E.g. if "product", then :meth:`.Computer.add_product` is called, which also automatically infers the correct dimensions for each input.
``key:``
   The key for the computed quantity.
``inputs:``
   A list of keys to which the computation is applied.
``args:`` (:class:`dict`, optional)
   Keyword arguments to the computation.
``add args:`` (:class:`dict`, optional)
   Keyword arguments to :meth:`.Computer.add` itself.


``report:``
-----------

.. autofunction:: report

Computer-specific configuration.

A ‘report’ is a concatenation of 1 or more other quantities.

Example
~~~~~~~

.. code-block:: yaml

    report:
    - key: foo
      members: [X, Y]


.. _config-units:

``units:``
----------

.. autofunction:: units

Global configuration.

Sub-keys:

``replace:`` (mapping of str -> str)
  Replace units before they are parsed by :doc:`pint <pint:index>`.
  Added to :obj:`.REPLACE_UNITS`.
``define:`` (:class:`str`)
  Multi-line block of unit definitions, added to the :mod:`pint` application registry so that units are recognized.
  See the pint :ref:`documentation on defining units <pint:defining>`.

.. code-block:: yaml

    units:
      replace:
        dollar: USD
      # YAML multi-line string
      define: |-
        pp = [person]
        tiny = 0.1 millimetre

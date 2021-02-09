Concepts and usage
******************

This page introduces the essential concepts of :mod:`genno` and demonstrates basic usage.
Click on the names of classes and methods to access complete descriptions in the :doc:`api`.

.. contents::
   :local:
   :backlinks: none

Quantity
========

:mod:`genno.Quantity` represents a sparse, multi-dimensional array with labels and units.
In research code it is common to use terms like ‘variables’, ‘parameters’, etc.; in :mod:`genno`, all data is ‘quantities’.

A Quantity has:

- 0 or more **dimensions**, with *labels* along those dimensions (e.g. specific years; the names of specific technologies);

  - A 0-dimensional Quantity is a single or ‘scalar’ (as opposed to ‘vector’) value.
- *sparse* coverage or “missingness,” i.e. there is not necessarily a value for each combination of labels; and
- associated *units*.

**Notation:**

.. math::

    \begin{align}
    A^{ij} & = \left[a_{i,j} \right] \\
    i & \in I \\
    j & \in J \\
    a_{i,j} & \in \left\{ \mathbb{R}, \text{NaN} \right\} \\
    a_{i,j} & [=]\, \text{units of X}
    \end{align}

Dimensionality of quantities
----------------------------

Quantities may have many dimensions.
For instance, suppose :math:`X^{abcdefghij}`, which has ten dimensions.
For some calculations, we may not care about some of these dimensions.
In this case, we don't really want the 10-dimensional quantity, but its **partial sum** over a few dimensions, while others are retained.

**Notation.**
Consider a quantity with three dimensions, :math:`A^{ijk}`, and another with two, :math:`B^{kl}`, and a scalar :math:`C`.
We define partial sums over every possible combination of dimensions:

.. math::

    \begin{array}
    AA^{ij} = \left[ a_{i,j} \right],
      & a_{i,j} = \sum_{k}{a_{i,j,k}} \ \forall \ i, j
      & \text{similarly } A^{ik}, A^{jk} \\
    A^{i} = \left[ a_i \right],
      & a_i = \sum_j\sum_{k}{a_{i,j,k}} \ \forall\  i
      & \text{similarly } A^j, A^k \\
    A = \sum_i\sum_j\sum_k{a_{i,j,k}}
      & & \text{(a scalar)}
    \end{array}


Note that :math:`A` and :math:`B` share one dimension, :math:`k`, but the other dimensions are distinct.
We specify that simple arithmetic operations result in a quantity whose dimensions are the union of the dimensions of the operands. In other words:

.. math::

    \begin{array}
    CC + A^{i} = X^{i} = \left[ x_{i} \right],
      & x_{i} = C + a_{i} \ \forall \ i \\
    A^{jk} \times B^{kl} = Y^{jkl} = \left[ y_{j,k,l} \right],
      & y_{j,k,l} = a_{j,k} \times b_{k,l} \ \forall \ j, k, l \\
    A^{j} - B^{j} = Z^{j} = \left[ z_{j} \right],
      & z_{j} = a_{j} - b_{j} \ \forall \ j \\
    \end{array}

As a result of this rule:

- The difference :math:`Z^j` has the same dimensionality as *both* of its operands.
- The sum :math:`X^i` has the same dimensionality as *one* of its operands.
- The product :math:`Y^{jkl}` has a different dimensonality from each of its operands.

These operations are called **broadcasting** and **alignment**: The scalar value :math:`C` is *broadcast* across all labels on the dimension :math:`i` that it lacks, in order to calculate :math:`x_i`.
:math:`A^{jk}` and :math:`B^{kl}` are *aligned* on matching values of :math:`k`, but *broadcast* over dimensions :math:`j` and :math:`l`, respectively.


Key
===

:class:`genno.Key` is used to *refer to* a Quantity, before it is computed.
For multi-dimensional calculations, we need keys that distinguish :math:`A^i`—the partial sum of :math:`A^{ijk}` used in the calculation of :math:`X^i`—from :math:`A^{jk}`—a *different* partial sum used in the calculation of :math:`Y^{jkl}`.
It is not sufficient to refer to both as `'A'`, since this is ambiguous about what calculation we want to perform.

A Key has a name, zero or more dimensions, and an optional tag:

.. ipython:: python

    from genno import Key

    # Quantity named 'A' dimensions i, j, k
    A_ijk = Key("A", ["i", "j", "k"])
    type(A_ijk)
    repr(A_ijk)
    str(A_ijk)

    # With different dimensions
    A_jk = Key("A", ["j", "k"])
    A_jk

Key has methods that allow producing related keys:

.. ipython:: python

    # Drop dimensions from a key
    A_ijk.drop("i")

    # Describe a key that is the product of two others; add a tag
    B_kl = Key("B", ["k", "l"])
    B_kl
    Key.product("Y", A_ijk.drop("i"), B_kl, tag="initial")

A Key object can also be produced by parsing a string representation:

.. ipython:: python

    Z_j = Key.from_str_or_key("Z:j")
    Z_j

    # Keys compare and hash() identically to their str() representation
    Z_j == "Z:j"

    Z_j == "Y:i-j-k"


Computer
========

:class:`.Computer` provides the main interface of :mod:`genno`.
Usage of a Computer involves two steps:

1. Use :meth:`.Computer.add` and other helper methods to describe all the tasks the Computer *might* perform.
2. Use :meth:`.Computer.get` to trigger the execution of one or more tasks.

This two-step process allows the :mod:`genno` to deliver good performance by skipping irrelevant tasks and avoiding re-computing intermediate results that are used in multiple places.

Graph
-----

:class:`.Computer` is built around a *graph* of *nodes* and *edges*; specifically, a directed, acyclic graph.
This means:

- Every edge has a direction; *from* one node *to* another.
- There are no recursive loops in the graph; i.e. no node is its own ancestor.

In the reporting graph, every node represents a **task**, usually a :class:`tuple` wherein the first element is a :class:`callable` like a function.
This callable can be:

- a numerical *calculation* operating on one or more Quantities;
- more generally, a *computation*, including other actions like transforming data formats, reading and writing files, writing plots, etc.

Other elements in the task
For a complete description of tasks, see :doc:`dask:spec`.

Every node has a unique *label*, describing the results of its task.
These labels can be :class:`.Key` (if the task produces a Quantity), :py:class:`str` (most other cases) or generally any other hashable object.

A node's computation may depend on certain inputs.
These are represented by the **edges** of the graph.

.. _describe-tasks:

Describe tasks
==============

For example, the following equation:

.. math:: C = A + B

…is represented by:

- A node named "A" that provides the value of A.
- A node named "B" that provides the value of B.
- A node named "C" that computes a sum of its inputs.
- An edge from "A" to 'C', indicating that the value of A is an input to C.
- An edge from "B" to 'C'.

To describe this using the Computer (step 1):

.. ipython:: python

    from genno import Computer

    # Create a new Computer object
    c = Computer()

    # Add two nodes
    # These have no inputs; they only return a literal value.
    c.add("A", 1)
    c.add("B", 2)

    # Add one node and two edges
    c.add("C", (lambda *inputs: sum(inputs), "A", "B"))

    # Equivalent, without parentheses
    c.add("C", lambda *inputs: sum(inputs), "A", "B")

To unpack this code:

- :meth:`Computer.add` is used to build the graph.
- The first argument to :meth:`add` is the label or key of the node; the description of what it will produce.
- The following arguments describe the task, calculation, or computation to be performed:

  - For nodes ‘A’ and ‘B’, these are simply a raw or literal value.
    When the node is executed, this value is returned.
  - For node ‘C’, it is a :class:`tuple` with 3 items: ``(lambda *inputs: sum(inputs), 'A', 'B')``.

    1. ``lambda *inputs: sum(inputs)``, is an `anonymous or ‘lambda’ function <https://doc.python.org/3/tutorial/controlflow.html#lambda-expressions>`_ that computes the sum of its inputs.
    2. The label ``"A"`` is a reference to another node. This indicates that there is a graph edge from node ``"A"`` into node ``"C"``.
    3. Same as (2)

All the keys in a Computer can be listed with :meth:`.keys`.


Execute tasks
=============

The task to produce "C", and any direct or indirect inputs required, is executed using :meth:`.Computer.get`:

.. ipython:: python

    c.get("C")

:meth:`Computer.describe` displays a simple textual trace of the tasks used in this computation.
A portion of the graph is printed out as a nested list:

.. ipython:: python

    print(c.describe("C"))

This description shows how :mod:`genno` traverses the graph in order to calculate the desired quantity:

1. The desired value is from node "C", which computes a function of some arguments.
2. The first argument is ``"A"``.
3. "A" is the name of another node.
4. Node "A" gives a literal value ``int(1)``, which is stored.
5. The Computer returns to "C" and moves on to the next argument, "B".
6. Steps 3 and 4 are repeated for "B", giving ``int(2)``.
7. All of the arguments to "C" have been processed.
8. The computation function for "C" is called.

   As arguments, instead of the strings "A" and "B", this function receives the computed :class:`int` values from steps 4 and 6 respectively.
9. The result is returned.

In this example, "A" and "B" are, at most, 1 step away from the node requested, and are each used once.
In more realistic examples, the graph can have:

- Long chains of calculations, each depending on the output of its ancestors, and/or
- Multiple connection, so that results like "A" are used by more than one child calculations.

However, the Computer still follows the same procedure to traverse the graph and calculate the results.

Computations
============

A computation is any Python function or callable that operates on Quantities or other data.
:mod:`genno.computations` includes many common computations; see the API documentation for descriptions of each.

The power of :mod:`genno` is the ability to link *any* code, no matter how complex, into the graph, and have it operate on the results of other code.
Tasks can perform complex tasks such as:

- Read in exogenous data, including over a network connection,
- Trigger output to files(s) or a database, or
- Execute user-defined methods.

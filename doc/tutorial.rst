Tutorial
********

‘Reporting’ is the term used in the MESSAGEix ecosystem to refer to any calculations performed *after* the MESSAGE mathematical optimization problem has been solved.

This tutorial introduces the reporting features provided by the ``ixmp`` and ``message_ix`` packages.
It was developed by Paul Natsuo Kishimoto (`@khaeru <https://github.com/khaeru>`_) for a MESSAGEix training workshop held at IIASA in October 2019.
Participants in the MESSAGEix workshops of June and September 2020 contributed feedback.

**Pre-requisites**

- You have the *MESSAGEix* framework installed and working.
- Complete tutorial Part 1 (``westeros_baseline.ipynb``)

  - Understand the following MESSAGEix terms: ‘variable’, ‘parameter’.
- Open the `‘Reporting’ page in the MESSAGEix documentation <https://docs.messageix.org/en/stable/reporting.html>`_; bookmark it or keep it open in a tab.
  Some text in this tutorial is drawn from that page, and it provides a concise reference for concepts explained below.

Introduction
============

What does ‘reporting’ include?
------------------------------

Individual modelers will make different distinctions between—on one hand—the internals of an optimization model and—on the other—reporting, ‘post-processing’, ‘analysis’, and other tasks.
Doing valid research using models like MESSAGE requires that we understand these differences clearly, as well as how we choose to communicate them.

For example, we might say: “The MESSAGE model shows that total secondary energy (electricity) output in Westeros in the year 720 is 9 GWa.”

But, if we are using the model from ``westeros_baseline.ipynb``:

1. The raw data from the ``Scenario``, after ``.solve()`` has been called, **only** tells us the ``ACT`` variable has certain values.
2. To get the 9 GWa figure, we must:

   1. Compute the product of activity (``ACT``, which is dimensionless) and output efficiency (``output`` in GWa/year), then
   2. Sum across the ``technology`` dimension, and finally
   3. Select the single value for the ``year`` 720.

In this example, steps A, B, and C under #2 are part of ‘reporting’.
Even a intuitive concept like “total secondary energy” is not a *direct* output of the model, but must be reported.

Next, we may want to create a plot of electricity output by year.
Some modelers consider this part of ‘reporting’; for others, ‘reporting’ is complete when the values needed for the plot are written to a file, which they can then use with their favourite plotting tool.

Reporting features in MESSAGEix
===============================

The reporting features in ``ixmp`` and ``message_ix`` are developed to support the complicated reporting and multiple workflows required by the IIASA Energy program for research projects involving large, detailed models such as the [MESSAGEix-GLOBIOM global model](https://docs.messageix.org/global/).
While powerful enough for this purpose, they are also intended to be user-friendly, flexible, and customizable.

The core class used for reporting is ``message_ix.Reporter``, which extends the class ``ixmp.Reporter``.
A reporting workflow has two steps:

1. Describe all computations the Reporter may handle, using ``Reporter.add()`` and other helper methods.
2. Triggering the computation of one or more quantities or reports, using ``Reporter.get()``.

This two-step process allows the Reporter to deliver good performance, by excluding unneeded computations and avoiding re-computing intermediate results that are used in multiple places.

Concepts: The Graph
===================

``ixmp.Reporter`` is built around a **graph** of *nodes* and *edges*; specifically, a *directed, acyclic graph*.
This means:

- Every edge has a direction; *from* one node *to* another.
- There are no recursive loops in the graph; i.e. no node is its own ancestor.

In the reporting graph, every **node** represents a numerical *calculation*—or, more generally, a *computation* (including other actions like manipulating data formats, writing files, etc.).
The node is labeled with the name of the quantity it produces, which is called a **key**.

A node's computation may depend on certain inputs.
These are represented by the **edges** of the graph.

For example, the following equation:

.. math:: C = A + B

…is represented by:

- A node named 'A' that provides the raw value of A.
- A node named 'B' that provides the raw value of B.
- A node named 'C' that computes a sum of its inputs.
- An edge from 'A' to 'C', indicating that the value of A is an input to C.
- An edge from 'B' to 'C'.

We use the Computer to describe this equation (step 1):

.. ipython:: python

    from genno import Computer

    # Create a new Computer object
    c = Computer()

    # Add two nodes
    # These have no outputs; they only return a literal value.
    c.add('A', 1)
    c.add('B', 2)

    # Add one node and two edges
    c.add('C', (lambda *inputs: sum(inputs), 'A', 'B'))


Here is a detailed explanation of what we just did:

- We use the ``add()`` method of a Reporter object to build the graph.
  (Remember: you can type ``Reporter.add?`` or ``rep.add?`` in a new cell to use Jupyter's help features; or look at the documentation page linked above.)
- The first argument to ``add()`` is the key of the node.
- The second argument describes the computation to be performed:

  - For nodes ‘A’ and ‘B’, these are simply the raw or literal value to be produced by the node.
  - For node ‘C’, it is a Python tuple with 3 items: ``(lambda *inputs: sum(inputs), 'A', 'B')``.

    Let's break that down further:

    - The first item, ``lambda *inputs: sum(inputs)``, is an anonymous function ([read more](https://doc.python.org/3/tutorial/controlflow.html#lambda-expressions)) that computes the sum of its inputs.
    - All the remaining items, ``'A', B'``, are keys for other nodes in the graph.

Next, let's trigger the calculation of ‘C’ (step 1), which gives the expected value:

.. ipython:: python

    c.get('C')

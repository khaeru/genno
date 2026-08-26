---
title: 'genno: Efficient, transparent calculation on N-dimensional data'
tags:
- Python
- energy
- transportation
authors:
- given-names: Paul Natsuo
  surname: Kishimoto
  orcid: 0000-0002-8578-753X
  affiliation: 1
affiliations:
- name: International Institute for Applied Systems Analysis
  index: 1
  ror: 02wfhk785
date: 5 September 2024
bibliography: paper.bib
---

# Summary

Research in the fields of energy and transport systems, including integrated assessment modeling of energy and climate policies, often requires complicated manipulations of input and output data that are *multi-dimensional*, *labeled*, *sparse*, and represent many measurable quantities with multiple units of measurement.

# Statement of need

Code for handling such data can be fragile and opaque, which makes the validation, reproduction and extension of research difficult.
In particular, adapting to new and revised input data, or refining model scenarios can involve extensive refactoring.

`genno` is a Python package that builds on `dask`, `pandas`, and `xarray` to provide an API for transparent description and efficient execution of operations on multi-dimensional data.

# Implementation and usage

`genno` extends the `dask` directed, acyclic graph (DAG) data structure, which describe tasks and their inputs using Python types.
While in `dask` these are used to distribute operations across multiple processes and nodes, in `genno` they are used to encode the data flow and manipulations in calculations expressed by the user.

The user first *prepares* a ‘Computer’ containing description of many tasks, and then *executes* one or more tasks.
`genno`, via `dask`, implements

In preparing calculations, the user may use *keys* that allow concise but unambiguous reference to quantities to be computed.

`genno` includes a large and growing library of fundamental *operators*, from which more complicated operations can be built up.

# Example applications

Two applications are described:

1. Input data preparation for the MESSAGEix-Transport model.

2. Integrated assessment modeling workflows.

# Acknowledgements

Many colleagues contributed to the initial design requirements for `genno`, including…

# References

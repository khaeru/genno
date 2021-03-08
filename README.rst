genno: efficient, transparent calculation on N-D data
*****************************************************

.. image:: https://img.shields.io/pypi/v/genno.svg
   :target: https://pypi.python.org/pypi/genno/
   :alt: PyPI version

.. image:: https://readthedocs.org/projects/genno/badge/?version=latest
   :target: https://genno.readthedocs.io/en/latest/?badge=latest
   :alt: Documentation build

.. image:: https://github.com/khaeru/genno/workflows/pytest/badge.svg
   :target: https://github.com/khaeru/genno/actions?query=workflow:pytest
   :alt: Build status

.. image:: https://codecov.io/gh/khaeru/genno/branch/main/graph/badge.svg
   :target: https://codecov.io/gh/khaeru/genno
   :alt: Test coverage

**genno** is a Python package for describing and executing complex calculations on labelled, multi-dimensional data.
It aims to make these calculations efficient, transparent, and easily validated as part of scientific research.

genno is built on high-quality Python data packages including ``dask``, ``xarray``, and ``pint``; and provides (current or planned) compatibility with packages including ``pandas``, ``matplotlib``, ``plotnine``, ``ixmp``, ``sdmx1``, and ``pyam``.

A 玄能 (*genno* or *gennoh*) is a type of hammer used in Japanese woodworking.
The package name is warning, by reference, to the adage “When you hold a hammer, every problem looks like a nail”: you shouldn't hit everything with ``genno``, but it is still a useful and versatile tool.


License
=======

Copyright © 2018–2021 genno developers.

Licensed under the GNU General Public License, version 3.0.

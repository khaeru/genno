"""Compatibility code for :mod:`pint`.

Notes:

- In unit expressions that contain multiple errors (e.g. undefined units *and* invalid
  syntax), the exact exception raised by pint can sometimes vary between releases.
- In pint 0.17, DefinitionSyntaxError is a subclass of SyntaxError.
  In pint 0.20, it is a subclass of ValueError.
"""
from typing import Type

import pint

try:
    PintError: Type[Exception] = pint.PintError
    ApplicationRegistry: Type = pint.ApplicationRegistry
except AttributeError:
    # Older versions of pint, e.g. 0.17
    PintError = type("PintError", (Exception,), {})
    ApplicationRegistry = pint.UnitRegistry


__all__ = [
    "ApplicationRegistry",
    "PintError",
]

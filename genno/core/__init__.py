import logging
from pathlib import Path

import pint
import yaml

from genno.util import REPLACE_UNITS

log = logging.getLogger(__name__)


def configure(path=None, **config):
    """Configure :mod:`genno` globally.

    Modifies global variables that affect the behaviour of *all* Computers and
    computations, namely :obj:`.REPLACE_UNITS`.

    Valid configuration keys—passed as *config* keyword arguments—include:

    Other Parameters
    ----------------
    units : mapping
        Configuration for handling of units. Valid sub-keys include:

        - **replace** (mapping of str -> str): replace units before they are
          parsed by :doc:`pint <pint:index>`. Added to :obj:`.REPLACE_UNITS`.
        - **define** (:class:`str`): block of unit definitions, added to the
          :mod:`pint` application registry so that units are recognized. See
          the pint :ref:`documentation on defining units <pint:defining>`.

    Warns
    -----
    UserWarning
        If *config* contains unrecognized keys.
    """
    config = _config_args(path, config)

    # Units
    units = config.get("units", {})

    # Define units
    registry = pint.get_application_registry()
    try:
        registry.define(units["define"].strip())
    except KeyError:
        pass
    except pint.DefinitionSyntaxError as e:
        log.warning(e)

    # Add replacements
    for old, new in units.get("replace", {}).items():
        REPLACE_UNITS[old] = new


def _config_args(path=None, keys={}):
    """Handle configuration arguments."""
    result = {}

    if path:
        # Load configuration from file
        path = Path(path)
        with open(path, "r") as f:
            result.update(yaml.safe_load(f))

        # Also store the directory where the configuration file was located
        result["config_dir"] = path.parent

    # Update with keys
    result.update(keys)

    return result

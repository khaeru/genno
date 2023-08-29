try:
    import pyam  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover
    HAS_PYAM = False
else:
    HAS_PYAM = True

import logging
from functools import partial
from typing import List

from genno import Computer, Key
from genno.config import handles
from genno.core.key import single_key

log = logging.getLogger(__name__)


@handles("iamc")
def iamc(c: Computer, info):
    """Handle one entry from the ``iamc:`` config section."""
    try:
        c.require_compat("pyam")
    except ModuleNotFoundError:  # pragma: no cover
        if not HAS_PYAM:
            log.warning("Missing pyam; configuration section 'iamc:' ignored")
            return
        else:
            raise

    from . import util

    # For each quantity, use a chain of computations to prepare it
    name = info.pop("variable")

    # Chain of keys produced: first entry is the key for the base quantity
    keys: List[Key] = [Key(info.pop("base"))]

    # Second entry is a simple rename
    keys.append(single_key(c.add_single(Key(name, keys[0].dims, keys[0].tag), keys[0])))

    # Optionally select a subset of data from the base quantity
    sel = info.get("select")
    if sel:
        keys.append(
            single_key(
                c.add_single(
                    keys[-1].add_tag("sel"),
                    (c.get_comp("select"), keys[-1], sel),
                    strict=True,
                )
            )
        )

    # Use a setting for the collapse callback function. This doesn't work from file,
    # since no way to define a Python function in JSON or YAML
    collapse_info = info.pop("collapse", {})
    collapse_func = collapse_info.pop("callback", util.collapse)

    # Use the Computer method to add the coversion step
    # NB convert_pyam() returns a single key when applied to a single key
    keys.append(
        single_key(
            c.add(
                keys[-1],
                "as_pyam",
                rename=info.pop("rename", {}),
                collapse=partial(collapse_func, **collapse_info),
                replace=info.pop("replace", {}),
                drop=set(info.pop("drop", [])) & set(keys[-1].dims),
                unit=info.pop("unit", None),
            )
        )
    )

    log.info(f"Add {repr(keys[-1])} from {repr(keys[0])}")
    log.debug(f"    {len(keys)} keys total")

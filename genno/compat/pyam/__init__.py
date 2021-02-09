try:
    import pyam  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover
    HAS_PYAM = False
else:
    HAS_PYAM = True

import logging
from functools import partial

from genno import Computer, Key, config
from genno.computations import group_sum

log = logging.getLogger(__name__)


@config.handles("iamc")
def iamc(c: Computer, info):
    """Handle one entry from the ``iamc:`` config section."""
    if not HAS_PYAM:  # pragma: no cover
        log.warning("Missing pyam; configuration section 'iamc:' ignored")
        return

    from .util import collapse

    # For each quantity, use a chain of computations to prepare it
    name = info.pop("variable")

    # Chain of keys produced: first entry is the key for the base quantity
    base = Key.from_str_or_key(info.pop("base"))
    keys = [base]

    # Second entry is a simple rename
    keys.append(c.add(Key(name, base.dims, base.tag), base))

    # Optionally select a subset of data from the base quantity
    sel = info.get("select")
    if sel:
        key = keys[-1].add_tag("sel")
        c.add(key, (c.get_comp("select"), keys[-1], sel), strict=True)
        keys.append(key)

    # Optionally aggregate data by groups
    gs = info.get("group_sum")
    if gs:
        key = keys[-1].add_tag("agg")
        task = (partial(group_sum, group=gs[0], sum=gs[1]), keys[-1])
        c.add(key, task, strict=True)
        keys.append(key)

    # Arguments for Computer.convert_pyam()
    args = dict(
        # Use 'ya' for the IAMC 'Year' column; unless YAML reporting config
        # includes a different dim under format/year_time_dim.
        year_time_dim=info.pop("year_time_dim", "ya"),
        drop=set(info.pop("drop", [])) & set(keys[-1].dims),
        replace_vars="iamc variable names",
    )

    # Optionally convert units
    args["unit"] = info.get("unit")

    # Remaining arguments are for the collapse() callback
    args["collapse"] = partial(collapse, var_name=name, **info)

    # Use the Computer method to add the coversion step
    iamc_keys = c.convert_pyam(keys[-1], **args)
    keys.extend(iamc_keys)

    # Revise the 'message:default' report to include the last key in the chain
    c.add("message:default", c.graph["message:default"] + (keys[-1],))

    log.info(f"Add {repr(keys[-1])} from {repr(keys[0])}")
    log.debug(f"    {len(keys)} keys total")

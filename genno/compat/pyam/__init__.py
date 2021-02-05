try:
    import pyam  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover
    HAS_PYAM = False
else:
    HAS_PYAM = True

import logging
from functools import partial

from genno import Computer, Key, config

log = logging.getLogger(__name__)


@config.handles("iamc")
def iamc(c: Computer, info):
    """Add one entry from the 'iamc:' section of a config file.

    Each entry uses :meth:`message_ix.reporting.Reporter.convert_pyam`
    (plus extra computations) to reformat data from the internal
    :class:`ixmp.reporting.Quantity` data structure into a
    :class:`pyam.IamDataFrame`.

    The entry *info* must contain:

    - **variable** (:class:`str`): variable name. This is used two ways: it
      is placed in 'Variable' column of the resulting IamDataFrame; and the
      reporting key to :meth:`~.Computer.get` the data frame is
      ``<variable>:iamc``.
    - **base** (:class:`str`): key for the quantity to convert.
    - **select** (:class:`dict`, optional): keyword arguments to
      :meth:`ixmp.reporting.Quantity.sel`.
    - **group_sum** (2-:class:`tuple`, optional): `group` and `sum` arguments
      to :func:`.group_sum`.
    - **year_time_dim** (:class:`str`, optional): Dimension to use for the IAMC
      'Year' or 'Time' column. Default 'ya'. (Passed to
      :meth:`~message_ix.reporting.Reporter.convert_pyam`.)
    - **drop** (:class:`list` of :class:`str`, optional): Dimensions to drop
      (→ convert_pyam).
    - **unit** (:class:`str`, optional): Force output in these units (→
      convert_pyam).

    Additional entries are passed as keyword arguments to :func:`.collapse`,
    which is then given as the `collapse` callback for
    :meth:`~message_ix.reporting.Reporter.convert_pyam`.

    :func:`.collapse` formats the 'Variable' column of the IamDataFrame.
    The variable name replacements from the 'iamc variable names:' section of
    the config file are applied to all variables.
    """
    if not HAS_PYAM:
        log.warning("Missing pyam; configuration section 'iamc:' ignored")

    from .util import collapse

    # For each quantity, use a chain of computations to prepare it
    name = info.pop("variable")

    # Chain of keys produced: first entry is the key for the base quantity
    base = Key.from_str_or_key(info.pop("base"))
    keys = [base]

    # Second entry is a simple rename
    keys.append(c.add(Key(name, base.dims, base.tag), base))

    # Optionally select a subset of data from the base quantity
    try:
        sel = info.pop("select")
    except KeyError:
        pass
    else:
        key = keys[-1].add_tag("sel")
        c.add(key, (c._get_comp("select"), keys[-1], sel), strict=True)
        keys.append(key)

    # Optionally aggregate data by groups
    try:
        gs = info.pop("group_sum")
    except KeyError:
        pass
    else:
        key = keys[-1].add_tag("agg")
        task = (partial(c._get_comp("group_sum"), group=gs[0], sum=gs[1]), keys[-1])
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
    try:
        args["unit"] = info.pop("unit")
    except KeyError:
        pass

    # Remaining arguments are for the collapse() callback
    args["collapse"] = partial(collapse, var_name=name, **info)

    # Use the Computer method to add the coversion step
    iamc_keys = c.convert_pyam(keys[-1], **args)
    keys.extend(iamc_keys)

    # Revise the 'message:default' report to include the last key in the chain
    c.add("message:default", c.graph["message:default"] + (keys[-1],))

    log.info(f"Add {repr(keys[-1])} from {repr(keys[0])}")
    log.debug(f"    {len(keys)} keys total")

import logging
from copy import copy
from functools import partial
from pathlib import Path

import pint
import yaml

from genno.core.computer import Computer
from genno.core.key import Key
import genno.computations as computations
from genno.util import REPLACE_UNITS

log = logging.getLogger(__name__)

HANDLERS = {}

CALLBACKS = []


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
    if path:
        config["path"] = path
    parse_config(None, config)


def handles(section_name, type_=list, keep=False, apply=True):
    """Decorator for a configuration section handler."""

    def wrapper(f):
        HANDLERS[section_name] = f
        setattr(f, "expected_type", type_)
        setattr(f, "keep_data", keep)
        setattr(f, "apply", apply)
        return f

    return wrapper


def parse_config(c: Computer, data: dict):
    # Assemble a queue of (args, kwargs) to Reporter.add()
    queue = []

    try:
        path = data.pop("path")
    except KeyError:
        pass
    else:
        # Load configuration from file
        path = Path(path)
        with open(path, "r") as f:
            data.update(yaml.safe_load(f))

        # Also store the directory where the configuration file was located
        if c is None:
            data["config_dir"] = path.parent
        else:
            # Early add to the graph
            c.graph["config"]["config_dir"] = path.parent

    to_pop = set()

    for section_name, section_data in data.items():
        try:
            handler = HANDLERS[section_name]
        except KeyError:
            log.warning(
                f"No handler for configuration section named {section_name}; ignored"
            )
            continue

        if not handler.keep_data:
            to_pop.add(section_name)

        if handler.apply is False:
            handler(c, section_data)
        elif handler.expected_type is list:
            queue.extend(
                (("apply", handler), dict(info=entry)) for entry in section_data
            )
        elif handler.expected_type is dict:
            queue.extend(
                (("apply", handler), dict(info=entry)) for entry in data.items()
            )
        else:
            raise NotImplementedError(handler.expected_type)

    for key in to_pop:
        data.pop(key)

    # Also add the callbacks to the queue
    queue.extend((("apply", cb), {}) for cb in CALLBACKS)

    if c:
        # Use Computer.add_queue() to process the entries.
        # Retry at most once; raise an exception if adding fails after that.
        c.add_queue(queue, max_tries=2, fail="raise")

        # Store configuration in the graph itself
        c.graph["config"] = data
    else:
        if len(queue):
            raise RuntimeError(
                "Cannot apply non-global configuration without a Computer"
            )


@handles("units", apply=False)
def units(c: Computer, info):

    # Define units
    registry = pint.get_application_registry()
    try:
        defs = info["define"].strip()
        registry.define(defs)
    except KeyError:
        pass
    except pint.DefinitionSyntaxError as e:
        log.warning(e)
    else:
        log.info(f"Apply global unit definitions {defs}")

    # Add replacements
    for old, new in info.get("replace", {}).items():
        log.info(f"Replace unit {repr(old)} with {repr(new)}")
        REPLACE_UNITS[old] = new


@handles("default", apply=False)
def default(c: Computer, info):
    c.default_key = info


@handles("files")
def file(c: Computer, info):
    # Files with exogenous data
    path = Path(info["path"])
    if not path.is_absolute():
        # Resolve relative paths relative to the directory containing the configuration
        # file
        path = c.graph["config"].get("config_dir", Path.cwd()) / path

    info["path"] = path

    c.add_file(**info)


@handles("alias", dict)
def alias(c: Computer, info):
    c.add(info[0], info[1])


@handles("aggregate")
def aggregate(c: Computer, info):
    """Add one entry from the 'aggregate:' section of a config file.

    Each entry uses :meth:`~..Computer.aggregate` to compute sums across
    labels within one dimension of a quantity.

    The entry *info* must contain:

    - **_quantities**: list of 0 or more keys for quantities to aggregate. The
      full dimensionality of the key(s) is inferred.
    - **_tag** (:class:`str`): new tag to append to the keys for the aggregated
      quantities.
    - **_dim** (:class:`str`): dimensions

    All other keys are treated as group names; the corresponding values are
    lists of labels along the dimension to sum.

    **Example:**

    .. code-block:: yaml

       aggregate:
       - _quantities: [foo, bar]
         _tag: aggregated
         _dim: a

         baz123: [baz1, baz2, baz3]
         baz12: [baz1, baz2]

    If the full dimensionality of the input quantities are ``foo:a-b`` and
    ``bar:a-b-c``, then :meth:`add_aggregate` creates the new quantities
    ``foo:a-b:aggregated`` and ``bar:a-b-c:aggregated``. These new quantities
    have the new labels ``baz123`` and ``baz12`` along their ``a`` dimension,
    with sums of the indicated values.
    """
    # Copy for destructive .pop()
    info = copy(info)

    quantities = c.infer_keys(info.pop("_quantities"))
    tag = info.pop("_tag")
    groups = {info.pop("_dim"): info}

    for qty in quantities:
        keys = c.aggregate(qty, tag, groups, sums=True)

        log.info(f"Add {repr(keys[0])} + {len(keys)-1} partial sums")


@handles("combine")
def combination(c: Computer, info):
    r"""Add one entry from the 'combine:' section of a config file.

    Each entry uses the :func:`~.combine` operation to compute a weighted sum
    of different quantities.

    The entry *info* must contain:

    - **key**: key for the new quantity, including dimensionality.
    - **inputs**: a list of dicts specifying inputs to the weighted sum. Each
      dict contains:

      - **quantity** (required): key for the input quantity.
        :meth:`add_combination` infers the proper dimensionality from the
        dimensions of `key` plus dimension to `select` on.
      - **select** (:class:`dict`, optional): selectors to be applied to the
        input quantity. Keys are dimensions; values are either single labels,
        or lists of labels. In the latter case, the sum is taken across these
        values, so that the result has the same dimensionality as `key`.
      - **weight** (:class:`int`, optional): weight for the input quantity;
        default 1.

    **Example.** For the following YAML:

    .. code-block:: yaml

       combine:
       - key: foo:a-b-c
         inputs:
         - quantity: bar
           weight: -1
         - quantity: baz::tag
           select: {d: [d1, d2, d3]}

    …:meth:`add_combination` infers:

    .. math::

       \text{foo}_{abc} = -1 \times \text{bar}_{abc}
       + 1 \times \sum_{d \in \{ d1, d2, d3 \}}{\text{baz}_{abcd}^\text{(tag)}}
       \quad \forall \quad a, b, c
    """
    # Split inputs into three lists
    quantities, select, weights = [], [], []

    # Key for the new quantity
    key = Key.from_str_or_key(info["key"])

    # Loop over inputs to the combination
    for i in info["inputs"]:
        # Required dimensions for this input: output key's dims, plus any
        # dims that must be selected on
        selector = i.get("select", {})
        dims = set(key.dims) | set(selector.keys())
        quantities.append(c.infer_keys(i["quantity"], dims))

        select.append(selector)
        weights.append(i.get("weight", 1))

    # Check for malformed input
    assert len(quantities) == len(select) == len(weights)

    # Computation
    c = tuple(
        [partial(computations.combine, select=select, weights=weights)] + quantities
    )

    added = c.add(key, c, strict=True, index=True, sums=True)

    log.info(f"Add {repr(key)} + {len(added)-1} partial sums")
    log.debug("    as combination of")
    log.debug(f"    {repr(quantities)}")


@handles("iamc")
def iamc_table(c: Computer, info):
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
    from genno.compat.pyam.util import collapse

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
        c.add(key, (computations.select, keys[-1], sel), strict=True)
        keys.append(key)

    # Optionally aggregate data by groups
    try:
        gs = info.pop("group_sum")
    except KeyError:
        pass
    else:
        key = keys[-1].add_tag("agg")
        task = (partial(computations.group_sum, group=gs[0], sum=gs[1]), keys[-1])
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


@handles("report")
def report(c: Computer, info):
    """Add items from the 'report' tree in the config file."""
    log.info(f"Add report {info['key']} with {len(info['members'])} table(s)")

    # Concatenate pyam data structures
    c.add(info["key"], tuple([c._get_comp("concat")] + info["members"]), strict=True)


@handles("general")
def general(c: Computer, info):
    """Add one entry from the 'general:' tree in the config file.

    This is, as the name implies, the most generalized section of the config
    file. Entry *info* must contain:

    - **comp**: this refers to the name of a computation that is available in the
      namespace of :mod:`message_data.reporting.computations` (be aware that it also
      imports all the computations from :doc:`ixmp <ixmp:reporting>` and
      doc:`message_ix <message_ix:reporting>`). E.g. if 'product', then
      :meth:`.Computer.add_product` is called, which also automatically
      infers the correct dimensions for each input.
    - **key**: the key for the computed quantity.
    - **inputs**: a list of keys to which the computation is applied.
    - **args** (:class:`dict`, optional): keyword arguments to the computation.
    - **add args** (:class:`dict`, optional): keyword arguments to
      :meth:`.Computer.add` itself.
    """
    inputs = c.infer_keys(info.get("inputs", []))

    if info["comp"] == "product":
        key = c.add_product(info["key"], *inputs)
        log.info(f"Add {repr(key)} using .add_product()")
    else:
        key = Key.from_str_or_key(info["key"])

        # Retrieve the function for the computation
        f = c._get_comp(info["comp"])

        log.info(f"Add {repr(key)} using {f.__name__}(...)")

        kwargs = info.get("args", {})
        task = tuple([partial(f, **kwargs)] + inputs)

        added = c.add(key, task, strict=True, index=True, sums=info.get("sums", False))

        if isinstance(added, list):
            log.info(f"    + {len(added)-1} partial sums")

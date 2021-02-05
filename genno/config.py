import logging
from copy import copy
from functools import partial
from pathlib import Path
from typing import Callable, List, Tuple

import pint
import yaml

import genno.computations as computations
from genno.core.computer import Computer
from genno.core.key import Key
from genno.util import REPLACE_UNITS

log = logging.getLogger(__name__)

HANDLERS = {}

CALLBACKS: List[Callable] = []


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
    queue: List[Tuple] = []

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
        else:  # pragma: no cover
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


@handles("alias", dict)
def alias(c: Computer, info):
    c.add(info[0], info[1])


@handles("combine")
def combine(c: Computer, info):
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
    task = tuple(
        [partial(computations.combine, select=select, weights=weights)] + quantities
    )

    added = c.add(key, task, strict=True, index=True, sums=True)

    log.info(f"Add {repr(key)} + {len(added)-1} partial sums")
    log.debug("    as combination of")
    log.debug(f"    {repr(quantities)}")


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

        if f is None:
            raise ValueError(info["comp"])

        log.info(f"Add {repr(key)} using {f.__name__}(...)")

        kwargs = info.get("args", {})
        task = tuple([partial(f, **kwargs)] + list(inputs))

        added = c.add(key, task, strict=True, index=True, sums=info.get("sums", False))

        if isinstance(added, list):
            log.info(f"    + {len(added)-1} partial sums")


@handles("report")
def report(c: Computer, info):
    """Add items from the 'report' tree in the config file."""
    log.info(f"Add report {info['key']} with {len(info['members'])} table(s)")

    # Concatenate pyam data structures
    c.add(info["key"], tuple([c._get_comp("concat")] + info["members"]), strict=True)


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

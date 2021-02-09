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

# Keys to be stored with no action.
STORE = set(["cache_path", "cache_skip"])

CALLBACKS: List[Callable] = []


def configure(path=None, **config):
    """Configure :mod:`genno` globally.

    Modifies global variables that affect the behaviour of *all* Computers and
    computations.

    Warns
    -----
    UserWarning
        If *config* contains unrecognized keys.

    See also
    --------
    :doc:`config`
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
            if section_name not in STORE:
                log.warning(
                    f"No handler for configuration section {repr(section_name)}; "
                    "ignored"
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
        c.graph["config"].update(data)
    else:
        if len(queue):
            raise RuntimeError(
                "Cannot apply non-global configuration without a Computer"
            )


@handles("aggregate")
def aggregate(c: Computer, info):
    """Handle one entry from the ``aggregate:`` config section."""
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
    """Handle one entry from the ``alias:`` config section."""
    c.add(info[0], info[1])


@handles("combine")
def combine(c: Computer, info):
    """Handle one entry from the ``combine:`` config section."""
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
    """Handle the ``default:`` config section."""
    c.default_key = info


@handles("files")
def files(c: Computer, info):
    """Handle one entry from the ``files:`` config section."""
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
    """Handle one entry from the ``general:`` config section."""
    inputs = c.infer_keys(info.get("inputs", []))

    if info["comp"] == "product":
        key = c.add_product(info["key"], *inputs)
        log.info(f"Add {repr(key)} using .add_product()")
    else:
        key = Key.from_str_or_key(info["key"])

        # Retrieve the function for the computation
        f = c.get_comp(info["comp"])

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
    """Handle one entry from the ``report:`` config section."""
    log.info(f"Add report {info['key']} with {len(info['members'])} table(s)")

    # Concatenate pyam data structures
    c.add(info["key"], tuple([c.get_comp("concat")] + info["members"]), strict=True)


@handles("units", apply=False)
def units(c: Computer, info):
    """Handle the ``units:`` config section."""

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

"""Resolve missing references using aliased target names, domains, and/or types.

Expanded from and with thanks for https://stackoverflow.com/a/62301461.
"""

import re
from typing import TYPE_CHECKING, Mapping, Optional

from docutils.nodes import Text
from sphinx.addnodes import pending_xref
from sphinx.ext.intersphinx import missing_reference

if TYPE_CHECKING:
    import sphinx.application


class Replacement:
    refdomain: Optional[str]
    reftype: Optional[str]
    reftarget: str
    text: Optional[str]

    # Identifier characters
    c = "[^`<>]+"

    # Match any of:
    # - ":domain:type:`text <target>`"
    # - ":domain:type:`target`"
    # - ":type:`text <target>`"
    # - ":type:`target`"
    # - "text <target>"
    # - "target"
    _target_expr = re.compile(
        rf"(:((?P<rd>{c}):)?(?P<rt>{c}):)?(`?)(?P<t_or_t>{c})(<(?P<target>{c})>)?\5"
    )

    def __init__(self, value: str) -> None:
        match = self._target_expr.fullmatch(value)
        assert match is not None
        self.refdomain, self.reftype, target_or_text, target = [
            match.group(k) for k in ("rd", "rt", "t_or_t", "target")
        ]
        if target is None:  # Target only, no replacement text
            self.reftarget, self.text = target_or_text, None
        else:  # Both target and text replacement
            self.reftarget, self.text = target, target_or_text.rstrip()


def apply_alias(config: Mapping[str, str], node) -> bool:
    """Apply `config` to `node`."""
    try:
        # Identify an alias expression matching the "reftarget" attribute of `node`
        expr = next(filter(lambda e: re.match(e, node["reftarget"]), config))
    except (KeyError, StopIteration):
        # No such attribute, or no matching expression → nothing to do
        return False

    # Unpack information about the replacement
    replace = Replacement(config[expr])

    # Resolve the ref by substituting the reftarget for the matching part
    node["reftarget"] = re.sub(f"^{expr}", replace.reftarget, node["reftarget"])

    # Rewrite the rendered text, reftype, and refdomain
    if replace.text:
        # Find the text node child
        text_node = next(iter(node.traverse(lambda n: n.tagname == "#text")))
        # Remove the old text node, add new text node with custom text
        text_node.parent.replace(text_node, Text(replace.text))
        # Force further processing to preserve this text node
        node["refexplicit"] = True
    if replace.reftype:
        node["reftype"] = replace.reftype
    if replace.refdomain:
        node["refdomain"] = replace.refdomain

    return True


def resolve_internal_aliases(app: "sphinx.application.Sphinx", doctree):
    """Handler for 'doctree-read' events."""
    config = app.config["reference_aliases"]
    for node in doctree.traverse(condition=pending_xref):
        apply_alias(config, node)


def resolve_intersphinx_aliases(app, env, node, contnode):
    """Handler for 'missing-reference' (intersphinx) events."""
    if apply_alias(app.config["reference_aliases"], node):
        # Delegate the rest of the work to intersphinx
        return missing_reference(app, env, node, contnode)


def setup(app: "sphinx.application.Sphinx"):
    """Connect :mod:`.rewrite_refs` event handlers."""

    app.add_config_value("reference_aliases", dict(), "")

    app.connect("doctree-read", resolve_internal_aliases)
    app.connect("missing-reference", resolve_intersphinx_aliases)

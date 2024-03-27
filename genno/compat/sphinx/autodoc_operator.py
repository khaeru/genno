from typing import TYPE_CHECKING

from sphinx.ext.autodoc import FunctionDocumenter

from genno.core.operator import Operator

if TYPE_CHECKING:
    import sphinx.application


class OperatorDocumenter(FunctionDocumenter):
    @classmethod
    def can_document_member(cls, member, membername, isattr, parent) -> bool:
        return isinstance(member, Operator) or super().can_document_member(
            member, membername, isattr, parent
        )


def setup(app: "sphinx.application.Sphinx"):
    """Configure :mod:`sphinx.ext.autodoc` to handle :class:`Operator` as functions."""
    app.add_autodocumenter(OperatorDocumenter, override=True)

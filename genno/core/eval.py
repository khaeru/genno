import ast
import numbers
from functools import partial, singledispatchmethod
from textwrap import dedent

from dask.core import quote

from genno.core.key import Key
from genno.core.quantity import Quantity

BINOP = {
    ast.Add: "add",
    ast.Div: "div",
    ast.Mult: "mul",
    ast.Pow: "pow",
    ast.Sub: "sub",
}


def unparse(node) -> str:
    """Compatibility with Python ≤3.9, where :func:`ast.unparse` is not yet defined."""
    try:
        return ast.unparse(node)
    except AttributeError:  # Python 3.8
        return repr(node)


class Parser:
    """Parser for :meth:`.Computer.eval`."""

    def __init__(self, computer):
        self.computer = computer
        self.queue = []
        self.new_keys = {}

    def parse(self, expr: str):
        # - Remove leading/trailing newlines
        # - Dedent the entire string
        # - Parse the expression; returns ast.Module
        # - Iterate over the statements in the module body
        for statement in ast.parse(dedent(expr.strip("\n"))).body:
            self.recurse(statement)

    def append(self, operands, task, kwargs=None):
        # Construct the target key (maybe anonymous)
        key = Key.product(self.current_target, *operands)

        self.anonymous_tag += 1
        if self.anonymous_tag == 0:
            self.new_keys[key.name] = key
        else:
            key = Key(key.name, key.dims, tag=f"_{self.anonymous_tag}")

        # Add a task to the queue
        self.queue.append(((key,) + task, kwargs or dict()))

        # Return the constructed key to the outer call
        return key

    @singledispatchmethod
    def recurse(self, node):
        # Something else, probably an ast.BinOp
        try:
            return self.computer.get_comp(BINOP[node.__class__])
        except KeyError:
            raise NotImplementedError(f"ast.{node.__class__.__name__}")

    @recurse.register
    def _(self, node: ast.Assign):
        # Identify the target
        if len(node.targets) != 1:
            raise NotImplementedError(f"Assign to {len(node.targets)} != 1 targets")
        elif not isinstance(node.targets[0], ast.Name):
            raise NotImplementedError(f"Assign to {node.targets[0].__class__.__name__}")

        # Store the current target name
        self.current_target = node.targets[0].id

        # Reset counter
        self.anonymous_tag = -1

        # Iteratively parse the right-hand side
        self.recurse(node.value)

    @recurse.register
    def _(self, node: ast.BinOp):
        # A binary operation: recurse both sides and identify the operation
        op = self.recurse(node.op)
        left = self.recurse(node.left)
        right = self.recurse(node.right)

        # Return the constructed key to the outer call
        return self.append((left, right), (op, left, right))

    @recurse.register
    def _(self, node: ast.UnaryOp):
        # A unary operation: look up some portions of a task
        if isinstance(node.op, ast.USub):
            op = (self.computer.get_comp("mul"), Quantity(-1.0))
        else:
            raise NotImplementedError(f"ast.{node.op.__class__.__name__}")

        # Recurse the operand
        operand = self.recurse(node.operand)

        # Return the constructed key to the outer call
        return self.append((operand,), op + (operand,))

    @recurse.register
    def _(self, node: ast.Call):
        if not isinstance(node.func, ast.Name):
            raise NotImplementedError(
                f"Call {unparse(node.func)}(…) instead of function"
            )

        # Get the computation function
        func = self.computer.get_comp(node.func.id)
        if func is None:
            raise NameError(f"No computation named {node.func.id!r}")

        # Recurse args and keyword args
        args = [self.recurse(arg) for arg in node.args]
        keywords = dict(map(self.recurse, node.keywords))

        return self.append(tuple(args), tuple([partial(func, **keywords)] + args))

    @recurse.register
    def _(self, node: ast.Constant):
        # A constant: convert to a Quantity
        if isinstance(node.value, numbers.Real):
            return Quantity(node.value)
        else:
            # Something else, e.g. a string
            return quote(node.value)

    @recurse.register
    def _(self, node: ast.Name):
        # A name: either the name of an existing key, or one created in this eval()
        # call
        return self.new_keys.get(node.id, None) or self.computer.full_key(node.id)

    @recurse.register
    def _(self, node: ast.keyword):
        if not isinstance(node.value, ast.Constant):
            raise NotImplementedError(
                f"Non-literal keyword arg {unparse(node.value)!r}"
            )
        return (node.arg, node.value.value)

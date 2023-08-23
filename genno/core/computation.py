from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from .computer import Computer


class Computation:
    """Base class for a callable with convenience methods."""

    # Use these specific attribute names to be intelligible to functools.partial()
    __slots__ = "func", "args", "keywords", "_add_tasks"

    def __init__(self, func):
        self.func = func
        self.args = ()
        self.kwargs = {}

    def __call__(self, *args, **kwargs):
        # Don't pass `self` to the callable
        return self.func(*args, **kwargs)

    def __repr__(self):
        return f"<{self.__class__.__name__}>"

    def helper(self, func: Callable) -> None:
        """Register `func` as the convenience method for adding task(s)."""
        self._add_tasks = func

    def add_tasks(self, c: "Computer", *args, **kwargs):
        """Invoke :attr:`_add_task` to add (a) task(s) to `c`."""
        if self._add_tasks is None:
            raise NotImplementedError

        return self._add_tasks(self, c, *args, **kwargs)


def computation(func: Callable):
    """Create a :class:`Computation` object that wraps `func`."""
    # Create a class and return an instance of it
    return type(func.__name__, (Computation,), {})(func)

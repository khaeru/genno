from typing import TYPE_CHECKING, Any, Callable, Dict, Tuple

if TYPE_CHECKING:
    from .computer import Computer
    from .key import KeyLike


class Computation:
    """Base class for a callable with convenience methods."""

    # Use these specific attribute names to be intelligible to functools.partial()
    __slots__ = "func", "args", "keywords", "_add_tasks"

    def __init__(self, func: Callable):
        self.func = func
        self.args = ()
        self.keywords: Dict[str, Any] = {}

    def __call__(self, *args, **kwargs):
        # Don't pass `self` to the callable
        return self.func(*args, **kwargs)

    def __repr__(self):
        return f"<{self.__class__.__name__}>"

    def helper(self, func: Callable[..., Tuple["KeyLike", ...]]) -> None:
        """Register `func` as the convenience method for adding task(s)."""
        self._add_tasks = func

    def add_tasks(self, c: "Computer", *args, **kwargs) -> Tuple["KeyLike", ...]:
        """Invoke :attr:`_add_task` to add (a) task(s) to `c`."""
        if self._add_tasks is None:
            raise NotImplementedError

        return self._add_tasks(self.func, c, *args, **kwargs)


def computation(func: Callable):
    """Create a :class:`Computation` object that wraps `func`."""
    # Create a class and return an instance of it
    return type(func.__name__, (Computation,), {})(func)

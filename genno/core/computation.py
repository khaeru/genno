from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from .computer import Computer


class Computation(ABC):
    """Abstract base class for a computation with convenience methods."""

    # Method for adding tasks to a Computer
    add_task: Callable

    @abstractmethod
    def __call__(self, *args, **kwargs):
        # Actual logic of the computation
        raise NotImplementedError  # pragma: no cover

    @classmethod
    def helper(cls, func: Callable) -> None:
        """Register `func` as the convenience method for creating tasks."""
        cls.add_task = func

    def add_task_method(self, c: "Computer", *args, **kwargs):
        """Invoke :attr:`add_task`; for use by Computer."""
        return self.add_task(c, *args, **kwargs)


def computation(func):
    """Create a :class:`Computation` object that wraps `func`."""

    # Create a class
    class Foo(Computation):
        __call__ = func

    # Return an instance of the class
    return Foo()

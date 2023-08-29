from functools import update_wrapper
from inspect import signature
from typing import TYPE_CHECKING, Any, Callable, ClassVar, Dict, Optional, Tuple, Union

if TYPE_CHECKING:
    from .computer import Computer
    from .key import KeyLike


class Operator:
    """Base class for a callable with convenience methods.

    Example
    -------
    >>> from genno import Operator
    >>>
    >>> @Operator.define
    ... def myfunc(q1: Quantity, q2: Quantity) -> Quantity:
    ...     # Operator code
    >>>
    >>> @myfunc.helper
    ... def add_myfunc(f, computer, *args, **kwargs):
    ...     # Custom code to add tasks to `computer`
    ...     # Perform checks or handle `args` and `kwargs`.
    """

    # Use these specific attribute names to be intelligible to functools.partial()
    #: Function or callable for the Operator.
    func: ClassVar[Callable]
    args = ()
    keywords: Dict[str, Any] = dict()

    #: Helper method to add tasks to a :class:`.Computer`. Register with :meth:`helper`,
    #: invoke with :meth:`add_tasks`.
    _add_tasks: ClassVar[Optional[Callable]] = None

    def __call__(self, *args, **kwargs):
        # The callable is stored as a static method; `self` is not passed
        return self.func(*args, **kwargs)

    def __eq__(self, other):
        """Compares equal to the wrapped `func`."""
        return other == self.func

    def __repr__(self):
        return f"<operator {self.__class__.__name__}>"

    @staticmethod
    def define(func: Callable) -> "Operator":
        """Create an Operator object that wraps `func`."""
        # This follows the pattern of using a metaclass, except compressed

        # - Create the class
        #   - Same name as func, subclass of Operator
        #   - Subclass of Operator
        #   - func is a static method
        #   - Signature of klass.__call__ is the signature of func.
        klass = type(
            func.__name__,
            (Operator,),
            {"func": staticmethod(func), "__signature__": signature(func)},
        )

        # Create an instance of the class, update __doc__ and other attributes, return
        # NB these are updated on the instance, not on `klass`, to satisfy Sphinx, which
        #    will skip documenting items that have the same __doc__ as their class
        return update_wrapper(klass(), func, updated=())

    def helper(
        self, func: Callable[..., Union["KeyLike", Tuple["KeyLike", ...]]]
    ) -> Callable:
        """Register `func` as the convenience method for adding task(s)."""
        self.__class__._add_tasks = staticmethod(func)
        return func

    def add_tasks(self, c: "Computer", *args, **kwargs) -> Tuple["KeyLike", ...]:
        """Invoke :attr:`_add_task` to add tasks to `c`."""
        if self._add_tasks is None:
            raise NotImplementedError

        return self._add_tasks(self.func, c, *args, **kwargs)

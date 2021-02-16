import warnings

# genno.core.sparsedataarray -> sparse 0.11.2 -> numba 0.52.0 -> numpy 1.20
warnings.filterwarnings(
    action="ignore",
    message="`np.long` is a deprecated alias for `np.compat.long`",
    module="numba.core",
)

from .config import configure  # noqa: E402
from .core.computer import Computer  # noqa: E402
from .core.exceptions import (  # noqa: E402
    ComputationError,
    KeyExistsError,
    MissingKeyError,
)
from .core.key import Key  # noqa: E402
from .core.quantity import Quantity  # noqa: E402

__all__ = [
    "ComputationError",
    "Computer",
    "Key",
    "KeyExistsError",
    "MissingKeyError",
    "Quantity",
    "configure",
]

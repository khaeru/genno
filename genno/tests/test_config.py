from genno.config import HANDLERS
from genno.compat.ixmp import HAS_IXMP


def test_handlers():
    # Expected config handlers are available
    assert len(HANDLERS) == 9 + HAS_IXMP
    for key, func in HANDLERS.items():
        assert isinstance(key, str) and callable(func)

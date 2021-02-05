import pytest

from genno import Computer, Key
from genno.config import HANDLERS
from genno.compat.ixmp import HAS_IXMP


def test_handlers():
    # Expected config handlers are available
    assert len(HANDLERS) == 9 + HAS_IXMP
    for key, func in HANDLERS.items():
        assert isinstance(key, str) and callable(func)


@pytest.mark.parametrize(
    "name",
    [
        "config-aggregate.yaml",
        # "config-combine.yaml",
        "config-general.yaml",
        "config-report.yaml",
        "config-units.yaml",
    ],
)
def test_config_file(test_data_path, name):
    """Test handling configuration file syntax using test data files."""
    c = Computer()

    # Set up test contents
    c.add(Key("X", list("abc")), None, index=True, sums=True)
    c.add(Key("Y", list("bcd")), None, index=True, sums=True)

    c.configure(path=test_data_path / name)

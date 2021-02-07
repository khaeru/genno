from pathlib import Path

import pytest

from genno.caching import PathEncoder, arg_hash


def test_PathEncoder():
    # Encodes pathlib.Path or subclass
    PathEncoder().default(Path.cwd())

    with pytest.raises(TypeError):
        PathEncoder().default(lambda foo: foo)


def test_arg_hash():
    # Expected value with no arguments
    assert "da39a3ee5e6b4b0d3255bfef95601890afd80709" == arg_hash()

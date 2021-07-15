from pathlib import Path

import pytest

from genno.caching import PathEncoder, arg_hash, hash_code


def test_PathEncoder():
    # Encodes pathlib.Path or subclass
    PathEncoder().default(Path.cwd())

    with pytest.raises(TypeError):
        PathEncoder().default(lambda foo: foo)


def test_arg_hash():
    # Expected value with no arguments
    assert "3345524abf6bbe1809449224b5972c41790b6cf2" == arg_hash()


def test_hash_code():
    def foo():
        x = 3
        return x + 1

    h1 = hash_code(foo)

    def foo():
        x = 3
        return x + 1

    # Functions with same code hash the same
    assert h1 == hash_code(foo)

    def foo():
        """Here's a docstring."""
        y = 3
        return y + 1

    # Larger differences → no match
    assert h1 != hash_code(foo)

    def bar():
        x = 4
        return x + 1

    # Functions with different code hash different
    assert hash_code(foo) != hash_code(bar)

    # Identical lambda functions hash the same
    l1 = lambda x: x + 2  # noqa: E731
    l2 = lambda y: y + 2  # noqa: E731

    assert hash_code(l1) == hash_code(l2)

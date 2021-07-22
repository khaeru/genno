from pathlib import Path

import pytest

from genno.caching import PathEncoder, hash_args, hash_code, hash_contents


def test_PathEncoder():
    # Encodes pathlib.Path or subclass
    PathEncoder().default(Path.cwd())

    with pytest.raises(TypeError):
        PathEncoder().default(lambda foo: foo)


def test_hash_args():
    # Expected value with no arguments
    assert "3345524abf6bbe1809449224b5972c41790b6cf2" == hash_args()


def test_hash_code():  # pragma: no cover
    # "no cover" applies to each of the function bodies below, never executed
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


def test_hash_contents(test_data_path):
    """:func:`.hash_contents` runs."""
    assert (
        "4d28f2d5bbfde96d3cd6fa91506315df27e41d8acc71dae38238b4afcde77e5460dce751a765e5"
        "c82e514b57d70d54dd61dfbc007846f05d8e9a2fd0a08d180b"
        == hash_contents(test_data_path / "input0.csv")
    )

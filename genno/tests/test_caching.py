import logging
import sys
from types import new_class

import numpy as np
import pandas as pd
import pytest

import genno.caching
from genno.caching import Encoder, decorate, hash_args, hash_code, hash_contents
from genno.core.attrseries import AttrSeries
from genno.core.sparsedataarray import SparseDataArray


class TestEncoder:
    @pytest.fixture
    def Bar(self):
        """Temporary class, for .test_{ignore,register}."""
        return new_class("Bar")

    def test_default(self, tmp_path):
        # Different paths encode differently
        assert Encoder().default(tmp_path / "x ") != Encoder().default(tmp_path / "y")

        # Lambda function is not encodable
        with pytest.raises(TypeError):
            Encoder().default(lambda foo: foo)

    @pytest.mark.parametrize("type_index", (0, 1))
    def test_ignore(self, monkeypatch, type_index, Bar):
        monkeypatch.setattr(genno.caching, "IGNORE", set())

        type_ = {0: Bar, 1: object}[type_index]

        # Raises TypeError for a type that can't be serialized
        with pytest.raises(TypeError):
            Encoder().default(Bar())

        # Ignore certain types
        Encoder.ignore(type_)

        # Now returns empty tuple
        assert tuple() == Encoder().default(Bar())

    def test_register(self, Bar):
        # Raises TypeError for a type that can't be serialized
        with pytest.raises(TypeError):
            Encoder().default(Bar())

        # Register a serializer
        @Encoder.register
        def _serialize_bar(o: Bar):
            return dict(bar=42)

        assert dict(bar=42) == Encoder().default(Bar())


@pytest.mark.parametrize(
    "value, suffix",
    (
        (np.array([3]), "pickle"),
        (pd.DataFrame(), "parquet"),
        (AttrSeries(), "parquet" if sys.version_info >= (3, 9) else "pickle"),
        pytest.param(
            SparseDataArray(), "parquet", marks=pytest.mark.xfail(raises=TypeError)
        ),
    ),
)
def test_decorate(caplog, tmp_path, value, suffix):
    """:func:`.decorate` works without a :class:`.Computer`."""

    caplog.set_level(logging.DEBUG)

    def myfunc():
        return value

    decorated = decorate(myfunc, cache_path=tmp_path)

    # Decorated function runs
    assert all(value == decorated())

    # Value was cached
    # NB use [1] not [-1] to accommodate a possible message about Parquet support
    assert caplog.messages[1].startswith("Cache miss for myfunc(<")
    files = list(tmp_path.glob(f"*.{suffix}"))
    assert 1 == len(files)

    # Cache hit on the second call
    assert all(value == decorated())
    assert caplog.messages[-1].startswith("Cache hit for myfunc(<")

    for f in files:
        f.unlink()


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
        # Function contains a lambda object
        x = 4
        k = filter(lambda foo: foo + 1, [])  # noqa: F841
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

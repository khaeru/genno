"""Tests of AttrSeries in particular."""
import pandas as pd
import pytest

from genno import Computer
from genno.core.attrseries import AttrSeries
from genno.testing import add_large_data


@pytest.fixture
def foo():
    idx = pd.MultiIndex.from_product([["a1", "a2"], ["b1", "b2"]], names=["a", "b"])
    yield AttrSeries([0, 1, 2, 3], index=idx)


@pytest.fixture
def bar():
    """A 1-dimensional quantity."""
    yield AttrSeries([0, 1], index=pd.Index(["a1", "a2"], name="a"))


def test_cumprod(bar):
    """AttrSeries.cumprod works with 1-dimensional quantities."""
    result = (1.1 + bar).cumprod("a")
    assert ("a",) == result.dims


def test_interp(foo):
    with pytest.raises(NotImplementedError):
        foo.interp(coords=dict(a=["a1", "a1.5", "a2"], b=["b1", "b1.5", "b2"]))


def test_rename(foo):
    assert foo.rename({"a": "c", "b": "d"}).dims == ("c", "d")


def test_sel(bar):
    # Selecting 1 element from 1-D parameter still returns AttrSeries
    result = bar.sel(a="a2")
    assert isinstance(result, AttrSeries)
    assert result.size == 1
    assert result.dims == ("a",)
    assert result.iloc[0] == 1


def test_squeeze(foo):
    assert foo.sel(a="a1").squeeze().dims == ("b",)
    assert foo.sel(a="a2", b="b1").squeeze().values == 2

    with pytest.raises(
        ValueError,
        match="dimension to squeeze out which has length greater than one",
    ):
        foo.squeeze(dim="b")

    with pytest.raises(KeyError, match="c"):
        foo.squeeze(dim="c")


def test_sum(foo, bar):
    # AttrSeries can be summed across all dimensions
    result = foo.sum(dim=["a", "b"])
    assert isinstance(result, AttrSeries)  # returns an AttrSeries
    assert result.size == 1  # with one element
    assert result.item() == 6  # that has the correct value

    # Sum with wrong dim raises ValueError
    with pytest.raises(ValueError):
        bar.sum("b")

    # Index with duplicate entries
    _baz = pd.DataFrame(
        [
            ["a1", "b1", "c1", 1.0],
            ["a1", "b1", "c1", 2.0],
            ["a2", "b2", "c3", 3.0],
            ["a2", "b2", "c4", 4.0],
            ["a3", "b3", "c5", 5.0],
        ],
        columns=["a", "b", "c", "value"],
    )
    # Fails with v1.13.0 AttrSeries.sum() using unstack()
    AttrSeries(_baz.set_index(["a", "b", "c"])["value"]).sum(dim="c")

    with pytest.raises(NotImplementedError):
        bar.sum("a", skipna=False)


@pytest.mark.skip
def test_sum_large(N_data=1e7):  # pragma: no cover
    """Test :meth:`.AttrSeries.sum` for large, sparse data."""
    # Create a single large AttrSeries
    c = Computer()
    add_large_data(c, 1, N_dims=11, N_data=N_data)
    qty = c.get("q_00")

    # Compute a sum()
    result = qty.sum(dim=["j", "k"])
    # print(result)  # DEBUG
    del result


def test_others(foo, bar):
    # Exercise other compatibility functions
    assert type(foo.to_frame()) is pd.DataFrame
    assert foo.drop("a").dims == ("b",)
    assert bar.dims == ("a",)

    with pytest.raises(NotImplementedError):
        bar.item("a2")
    with pytest.raises(ValueError):
        bar.item()

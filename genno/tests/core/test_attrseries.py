"""Tests of AttrSeries in particular."""
import pandas as pd
import pytest

from genno.core.attrseries import AttrSeries


@pytest.fixture
def foo():
    idx = pd.MultiIndex.from_product([["a1", "a2"], ["b1", "b2"]], names=["a", "b"])
    yield AttrSeries([0, 1, 2, 3], index=idx)


@pytest.fixture
def bar():
    yield AttrSeries([0, 1], index=pd.Index(["a1", "a2"], name="a"))


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


def test_others(foo, bar):
    # Exercise other compatibility functions
    assert type(foo.to_frame()) is pd.DataFrame
    assert foo.drop("a").dims == ("b",)
    assert bar.dims == ("a",)

    with pytest.raises(NotImplementedError):
        bar.item("a2")
    with pytest.raises(ValueError):
        bar.item()

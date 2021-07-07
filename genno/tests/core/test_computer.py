import logging
import re
from functools import partial

import numpy as np
import pandas as pd
import pint
import pytest
import xarray as xr

from genno import (
    ComputationError,
    Computer,
    Key,
    KeyExistsError,
    MissingKeyError,
    Quantity,
    computations,
)
from genno.core.attrseries import AttrSeries
from genno.testing import (
    add_dantzig,
    add_test_data,
    assert_qty_allclose,
    assert_qty_equal,
)

log = logging.getLogger(__name__)


def test_cache(caplog, tmp_path, test_data_path, ureg):
    caplog.set_level(logging.INFO)

    # Set the cache path
    c = Computer(cache_path=tmp_path)

    # Arguments and keyword arguments for the computation. These are hashed to make the
    # cache key
    args = (test_data_path / "input0.csv", "foo")
    kwargs = dict(bar="baz")

    # Expected value
    exp = computations.load_file(test_data_path / "input0.csv")
    exp.attrs["args"] = repr(args)
    exp.attrs["kwargs"] = repr(kwargs)

    def myfunc1(*args, **kwargs):
        # Send something to the log for caplog to pick up when the function runs
        log.info("myfunc executing")
        result = computations.load_file(args[0])
        result.attrs["args"] = repr(args)
        result.attrs["kwargs"] = repr(kwargs)
        return result

    # Add to the Computer
    c.add("test 1", (partial(myfunc1, *args, **kwargs),))

    # Returns the expected result
    assert_qty_equal(exp, c.get("test 1"))

    # Function was executed
    assert "myfunc executing" in caplog.messages

    # Same function, but cached
    @c.cache
    def myfunc2(*args, **kwargs):
        return myfunc1(*args, **kwargs)

    # Add to the computer
    c.add("test 2", (partial(myfunc2, *args, **kwargs),))

    # First time computed, returns the expected result
    caplog.clear()
    assert_qty_equal(exp, c.get("test 2"))

    # Function was executed
    assert "myfunc executing" in caplog.messages

    # 1 cache file was created in the cache_path
    files = list(tmp_path.glob("*.pkl"))
    assert 1 == len(files)

    # File name includes the full hash; retrieve it
    hash = files[0].stem.split("-")[-1]

    # Cache miss was logged
    assert f"Cache miss for myfunc2(<{hash[:8]}…>)" in caplog.messages

    # Second time computed, returns the expected result
    caplog.clear()
    assert_qty_equal(exp, c.get("test 2"))

    # Value was loaded from the cache file
    assert f"Cache hit for myfunc2(<{hash[:8]}…>)" in caplog.messages
    # The function was NOT executed
    assert not ("myfunc executing" in caplog.messages)

    # With cache_skip
    caplog.clear()
    c.configure(cache_skip=True)
    c.get("test 2")

    # Function is executed
    assert "myfunc executing" in caplog.messages

    # With no cache_path set
    c.graph["config"].pop("cache_path")

    caplog.clear()
    c.get("test 2")
    assert "'cache_path' configuration not set; using " in caplog.messages[0]


def test_contains():
    """:meth:`Computer.__contains__` works regardless of dimension order."""
    c = Computer()
    c.add("a:x-y", 1)

    assert "a:x-y" in c
    assert "a:y-x" in c


def test_get():
    """Computer.get() using a default key."""
    c = Computer()

    # No default key is set
    with pytest.raises(ValueError, match="no default reporting key set"):
        c.get()

    c.configure(default="foo")
    c.add("foo", 42)

    # Default key is used
    assert c.get() == 42


def test_order():
    """:meth:`.describe` and :meth:`.get` work with dimensions in a different order."""
    c = Computer()

    # add() and describe() with dimensions in a different order. The output matches the
    # order given to add().
    c.add("a:x-y", 1.1, index=True)
    assert "'a:x-y':\n- 1.1" == c.describe("a:y-x")

    # Opposite order
    with pytest.raises(KeyExistsError):
        # Raises an exception with strict=True
        c.add("a:y-x", 1.1, strict=True)

    # Now replace
    c.add("a:y-x", 1.1)
    # Output matches order given to describe()
    assert "'a:x-y':\n- 1.1" == c.describe("a:x-y")

    # get() works with key in either order
    assert 1.1 == c.get("a:y-x")
    assert 1.1 == c.get("a:x-y")

    c.add("b:x-y", 2.2)

    def func(*args):
        print("sum args", args)
        return sum(args)

    # Dimensions in correct order
    key = c.add("c", func, "a:x-y", "b:x-y", strict=True)
    assert np.isclose(3.3, c.get(key))

    # Dimensions in different order
    c.graph.pop("c")
    key = c.add("c", func, "a:y-x", "b:y-x", strict=True)
    assert np.isclose(3.3, c.get(key))


def test_get_comp():
    # Invalid name for a function returns None
    assert Computer().get_comp(42) is None


def test_infer_keys():
    c = Computer()

    X_key = Key("X", list("abcdef"))
    Y_key = Key("Y", list("defghi"), "tag")

    c.add(X_key, None, index=True, sums=True)
    c.add(Y_key, None, index=True)

    # Single key
    assert X_key == c.infer_keys("X::")

    # Single Key with desired dimensions
    assert Key("X", list("ace")) == c.infer_keys("X::", dims="aceq")

    # Single string key with desired dimensions
    assert Key("X", list("ace")) == c.infer_keys("X", dims="aceq")

    # Multiple keys with tag and desired dimensions
    assert (Key("X", list("adf")), Key("Y", list("dfi"), "tag")) == c.infer_keys(
        ["X::", "Y::tag"], dims="adfi"
    )

    # Value with missing tag does not produce a match
    with pytest.raises(KeyError):
        c.infer_keys("Y::")


def test_require_compat():
    c = Computer()
    with pytest.raises(
        ModuleNotFoundError,
        match="No module named '_test', required by genno.compat._test",
    ):
        c.require_compat("_test")


def test_add0():
    """Adding computations that refer to missing keys raises KeyError."""
    c = Computer()
    c.add("a", 3)
    c.add("d", 4)

    # Invalid: value before key
    with pytest.raises(TypeError):
        c.add(42, "a")

    # Adding an existing key with strict=True
    with pytest.raises(KeyExistsError, match=r"key 'a' already exists"):
        c.add("a", 5, strict=True)

    def gen(other):  # pragma: no cover
        """A generator for apply()."""
        return (lambda a, b: a * b, "a", other)

    def msg(*keys):
        """Return a regex for str(MissingKeyError(*keys))."""
        return re.escape(f"required keys {repr(tuple(keys))} not defined")

    # One missing key
    with pytest.raises(MissingKeyError, match=msg("b")):
        c.add_product("ab", "a", "b")

    # Two missing keys
    with pytest.raises(MissingKeyError, match=msg("c", "b")):
        c.add_product("abc", "c", "a", "b")

    # Using apply() targeted at non-existent keys also raises an Exception
    with pytest.raises(MissingKeyError, match=msg("e", "f")):
        c.apply(gen, "d", "e", "f")

    # add(..., strict=True) checks str or Key arguments
    g = Key("g", "hi")
    with pytest.raises(MissingKeyError, match=msg("b", g)):
        c.add("foo", (computations.product, "a", "b", g), strict=True)

    # aggregate() and disaggregate() call add(), which raises the exception
    with pytest.raises(MissingKeyError, match=msg(g)):
        c.aggregate(g, "tag", "i")
    with pytest.raises(MissingKeyError, match=msg(g)):
        c.disaggregate(g, "j")

    # add(..., sums=True) also adds partial sums
    c.add("foo:a-b-c", [], sums=True)
    assert "foo:b" in c

    # add(name, ...) where name is the name of a computation
    c.add("select", "bar", "a", indexers={"dim": ["d0", "d1", "d2"]})

    # add(name, ...) with keyword arguments not recognized by the computation
    # raises an exception
    msg = "unexpected keyword argument 'bad_kwarg'"
    with pytest.raises(TypeError, match=msg):
        c.add("select", "bar", "a", bad_kwarg="foo", index=True)


def test_add1():
    """:meth:`._rewrite_comp` is a no-op for types other that list and tuple."""
    Computer().add("a", 1, strict=True)
    Computer().add("a", pd.DataFrame(), strict=True)


def test_add_queue(caplog):
    c = Computer()
    c.add("foo-0", (lambda x: x, 42))

    # A computation
    def _product(a, b):
        return a * b

    # A queue of computations to add. Only foo-1 succeeds on the first pass;
    # only foo-2 on the second pass, etc.
    strict = dict(strict=True)
    queue = [
        (("foo-4", _product, "foo-3", 10), strict),
        (("foo-3", _product, "foo-2", 10), strict),
        (("foo-2", _product, "foo-1", 10), strict),
        (("foo-1", _product, "foo-0", 10), {}),
    ]

    # Maximum 3 attempts → foo-4 fails on the start of the 3rd pass
    with pytest.raises(MissingKeyError, match="foo-3"):
        c.add(queue, max_tries=3, fail="raise")

    # But foo-2 was successfully added on the second pass, and gives the
    # correct result
    assert c.get("foo-2") == 42 * 10 * 10

    # Failures without raising an exception
    c.add(queue, max_tries=3, fail=logging.INFO)
    assert "Failed 3 times to add:" in caplog.messages

    # NB the following works in Python >= 3.7, but not 3.6, where it ends ",)"
    # assert "    with MissingKeyError('foo-3')" in caplog.messages
    expr = re.compile(r"    with MissingKeyError\('foo-3',?\)")
    assert any(expr.match(m) for m in caplog.messages)

    queue = [((Key("bar", list("abcd")), 10), dict(sums=True))]
    added = c.add_queue(queue)
    assert 16 == len(added)


def test_apply():
    # Computer with two scalar values
    c = Computer()
    c.add("foo", (lambda x: x, 42))
    c.add("bar", (lambda x: x, 11))

    N = len(c.keys())

    # A computation
    def _product(a, b):
        return a * b

    # A generator function that yields keys and computations
    def baz_qux(key):
        yield key + ":baz", (_product, key, 0.5)
        yield key + ":qux", (_product, key, 1.1)

    # Apply the generator to two targets
    c.apply(baz_qux, "foo")
    c.apply(baz_qux, "bar")

    # Four computations were added
    N += 4
    assert len(c.keys()) == N
    assert c.get("foo:baz") == 42 * 0.5
    assert c.get("foo:qux") == 42 * 1.1
    assert c.get("bar:baz") == 11 * 0.5
    assert c.get("bar:qux") == 11 * 1.1

    # A generator that takes two arguments
    def twoarg(key1, key2):
        yield key1 + "__" + key2, (_product, key1, key2)

    c.apply(twoarg, "foo:baz", "bar:qux")

    # One computation added
    N += 1
    assert len(c.keys()) == N
    assert c.get("foo:baz__bar:qux") == 42 * 0.5 * 11 * 1.1

    # A useless generator that does nothing
    def useless():
        return

    c.apply(useless)

    # Also call via add()
    c.add("apply", useless)

    # Nothing new added
    assert len(c.keys()) == N

    # Adding with a generator that takes Computer as the first argument
    def add_many(c_: Computer, max=5):
        [c_.add(f"foo{x}", _product, "foo", x) for x in range(max)]

    c.apply(add_many, max=10)

    # Function was called, adding keys
    assert len(c.keys()) == N + 10

    # Keys work
    assert c.get("foo9") == 42 * 9


def test_add_product(ureg):
    c = Computer()

    *_, x = add_test_data(c)

    # add_product() works
    key = c.add_product("x squared", "x", "x", sums=True)

    # Product has the expected dimensions
    assert key == "x squared:t-y"

    # Product has the expected value
    assert_qty_equal(Quantity(x * x, units=ureg.kilogram ** 2), c.get(key))

    # add('product', ...) works
    key = c.add("product", "x_squared", "x", "x", sums=True)


def test_aggregate():
    c = Computer()

    t, t_foo, t_bar, x = add_test_data(c)

    # Define some groups
    t_groups = {"foo": t_foo, "bar": t_bar, "baz": ["foo1", "bar5", "bar6"]}

    # Use the computation directly
    agg1 = computations.aggregate(Quantity(x), {"t": t_groups}, True)

    # Expected set of keys along the aggregated dimension
    assert set(agg1.coords["t"].values) == set(t) | set(t_groups.keys())

    # Sums are as expected
    assert_qty_allclose(agg1.sel(t="foo", drop=True), x.sel(t=t_foo).sum("t"))
    assert_qty_allclose(agg1.sel(t="bar", drop=True), x.sel(t=t_bar).sum("t"))
    assert_qty_allclose(
        agg1.sel(t="baz", drop=True), x.sel(t=["foo1", "bar5", "bar6"]).sum("t")
    )

    # Use Computer convenience method
    key2 = c.aggregate("x:t-y", "agg2", {"t": t_groups}, keep=True)

    # Group has expected key and contents
    assert key2 == "x:t-y:agg2"

    # Aggregate is computed without error
    agg2 = c.get(key2)

    assert_qty_equal(agg1, agg2)

    # Add aggregates, without keeping originals
    key3 = c.aggregate("x:t-y", "agg3", {"t": t_groups}, keep=False)

    # Distinct keys
    assert key3 != key2

    # Only the aggregated and no original keys along the aggregated dimension
    agg3 = c.get(key3)
    assert set(agg3.coords["t"].values) == set(t_groups.keys())

    with pytest.raises(NotImplementedError):
        # Not yet supported; requires two separate operations
        c.aggregate("x:t-y", "agg3", {"t": t_groups, "y": [2000, 2010]})


def test_check_keys():
    """:meth:`.check_keys` succeeds even with dimensions in a different order."""
    c = Computer()

    # Add with string keys
    c.add("a:y-x", None)
    c.add("b:z-y", None)

    assert [Key("a", "xy"), Key("b", "zy")] == c.check_keys("a:x-y", "b:z-y")

    # All orders
    c.check_keys("a:y-x", "a:x-y", "b:z-y", "b:y-z")

    # Non-existent keys, both bare strings and those parsed to Key()
    assert c.check_keys("foo", "foo:bar-baz", action="return") is None

    # Check a lookup using the index
    c.add("a:y-x:foo", index=True)
    assert [Key("a", "yx", "foo")] == c.check_keys("a::foo")


def test_dantzig(ureg):
    c = Computer()
    add_dantzig(c)

    # Partial sums are available automatically (d is defined over i and j)
    d_i = c.get("d:i")

    # Units pass through summation
    assert d_i.attrs["_unit"] == ureg.kilometre

    # Summation across all dimensions results a 1-element Quantity
    d = c.get("d:")
    assert d.shape == ((1,) if Quantity._get_class() is AttrSeries else tuple())
    assert d.size == 1
    assert np.isclose(d.values, 11.7)

    # Weighted sum
    weights = Quantity(
        xr.DataArray([1, 2, 3], coords=["chicago new-york topeka".split()], dims=["j"])
    )
    new_key = c.aggregate("d:i-j", "weighted", "j", weights)

    # ...produces the expected new key with the summed dimension removed and
    # tag added
    assert new_key == "d:i:weighted"

    # ...produces the expected new value
    obs = c.get(new_key)
    d_ij = c.get("d:i-j")
    exp = Quantity(
        (d_ij * weights).sum(dim=["j"]) / weights.sum(dim=["j"]),
        attrs=d_ij.attrs,
    )

    assert_qty_equal(exp, obs)

    # Disaggregation with explicit data
    # (cases of canned food 'p'acked in oil or water)
    shares = xr.DataArray([0.8, 0.2], coords=[["oil", "water"]], dims=["p"])
    new_key = c.disaggregate("b:j", "p", args=[Quantity(shares)])

    # ...produces the expected key with new dimension added
    assert new_key == "b:j-p"

    b_jp = c.get("b:j-p")

    # Units pass through disaggregation
    assert b_jp.attrs["_unit"] == ureg.case

    # Set elements are available
    assert c.get("j") == ["new-york", "chicago", "topeka"]

    # 'all' key retrieves all quantities
    exp = set(
        "a b d f x z cost cost-margin demand demand-margin supply supply-margin".split()
    )
    assert all(qty.name in exp for qty in c.get("all"))

    # Shorthand for retrieving a full key name
    assert c.full_key("d") == "d:i-j" and isinstance(c.full_key("d"), Key)


def test_describe(test_data_path, capsys, ureg):
    c = Computer()
    add_dantzig(c)

    # Describe one key
    desc1 = """'d:i':
- sum(dimensions=['j'], weights=None, ...)
- 'd:i-j':
  - get_test_quantity(<d:i-j>, ...)"""
    assert desc1 == c.describe("d:i")

    # With quiet=True (default), nothing is printed to stdout
    out1, _ = capsys.readouterr()
    assert "" == out1

    # With quiet=False, description is also printed to stdout
    assert desc1 == c.describe("d:i", quiet=False)
    out1, _ = capsys.readouterr()
    assert desc1 + "\n" == out1

    # Description of all keys is as expected
    desc2 = (test_data_path / "describe.txt").read_text()
    assert desc2 == c.describe(quiet=False) + "\n"

    # Since quiet=False, description is also printed to stdout
    out2, _ = capsys.readouterr()
    assert desc2 == out2


def test_disaggregate():
    c = Computer()
    foo = Key("foo", ["a", "b", "c"])
    c.add(foo, "<foo data>")
    c.add("d_shares", "<share data>")

    # Disaggregation works
    c.disaggregate(foo, "d", args=["d_shares"])

    assert "foo:a-b-c-d" in c.graph
    assert c.graph["foo:a-b-c-d"] == (
        computations.disaggregate_shares,
        "foo:a-b-c",
        "d_shares",
    )

    # Invalid method
    with pytest.raises(ValueError):
        c.disaggregate(foo, "d", method="baz")

    with pytest.raises(TypeError):
        c.disaggregate(foo, "d", method=None)


def test_file_io(tmp_path):
    c = Computer()

    # Path to a temporary file
    p = tmp_path / "foo.txt"

    # File can be added to the Computer before it is created, because the file
    # is not read until/unless required
    k1 = c.add_file(p)

    # File has the expected key
    assert k1 == "file:foo.txt"

    # Add some contents to the file
    p.write_text("Hello, world!")

    # The file's contents can be read through the Computer
    assert c.get("file:foo.txt") == "Hello, world!"

    # Write the resulting quantity to a different file
    p2 = tmp_path / "bar.txt"
    c.write("file:foo.txt", p2)

    # Write using a string path
    c.write("file:foo.txt", str(p2))

    # The Computer produces the expected output file
    assert p2.read_text() == "Hello, world!"


def test_file_formats(test_data_path, tmp_path):
    c = Computer()

    expected = Quantity(
        pd.read_csv(test_data_path / "input0.csv", index_col=["i", "j"])["value"],
        units="km",
    )

    # CSV file is automatically parsed to xr.DataArray
    p1 = test_data_path / "input0.csv"
    k = c.add_file(p1, units=pint.Unit("km"))
    assert_qty_equal(c.get(k), expected)

    # Dimensions can be specified
    p2 = test_data_path / "input1.csv"
    k2 = c.add_file(p2, dims=dict(i="i", j_dim="j"))
    assert_qty_equal(c.get(k), c.get(k2))

    # Units are loaded from a column
    assert c.get(k2).attrs["_unit"] == pint.Unit("km")

    # Specifying units that do not match file contents → ComputationError
    c.add_file(p2, key="bad", dims=dict(i="i", j_dim="j"), units="kg")
    with pytest.raises(ComputationError):
        c.get("bad")

    # Write to CSV
    p3 = tmp_path / "output.csv"
    c.write(k, p3)

    # Output is identical to input file, except for order
    assert sorted(p1.read_text().split("\n")) == sorted(p3.read_text().split("\n"))

    # Write to Excel
    p4 = tmp_path / "output.xlsx"
    c.write(k, p4)
    # TODO check the contents of the Excel file


def test_full_key():
    c = Computer()

    # Without index, the full key cannot be retrieved
    c.add("a:i-j-k", [])
    with pytest.raises(KeyError, match="a"):
        c.full_key("a")

    # Using index=True adds the full key to the index
    c.add("a:i-j-k", [], index=True)
    assert c.full_key("a") == "a:i-j-k"

    # The full key can be retrieved by giving only some of the indices
    assert c.full_key("a:j") == "a:i-j-k"

    # Same with a tag
    c.add("a:i-j-k:foo", [], index=True)
    # Original and tagged key can both be retrieved
    assert c.full_key("a") == "a:i-j-k"
    assert c.full_key("a::foo") == "a:i-j-k:foo"


def test_units(ureg):
    """Test handling of units within computations."""
    c = Computer()

    assert isinstance(c.unit_registry, pint.UnitRegistry)

    # Create some dummy data
    dims = dict(coords=["a b c".split()], dims=["x"])
    c.add("energy:x", Quantity(xr.DataArray([1.0, 3, 8], **dims), units="MJ"))
    c.add("time", Quantity(xr.DataArray([5.0, 6, 8], **dims), units="hour"))
    c.add("efficiency", Quantity(xr.DataArray([0.9, 0.8, 0.95], **dims)))

    # Aggregation preserves units
    c.add("energy", (computations.sum, "energy:x", None, ["x"]))
    assert c.get("energy").attrs["_unit"] == ureg.parse_units("MJ")

    # Units are derived for a ratio of two quantities
    c.add("power", (computations.ratio, "energy:x", "time"))
    assert c.get("power").attrs["_unit"] == ureg.parse_units("MJ/hour")

    # Product of dimensioned and dimensionless quantities keeps the former
    c.add("energy2", (computations.product, "energy:x", "efficiency"))
    assert c.get("energy2").attrs["_unit"] == ureg.parse_units("MJ")


@pytest.mark.parametrize("suffix", [".json", ".yaml"])
def test_read_config(test_data_path, suffix):
    c = Computer()

    # Configuration can be read from file
    c.configure(test_data_path.joinpath("config-0").with_suffix(suffix))

    # Data from configured file is available
    assert c.get("d_check").loc["seattle", "chicago"] == 1.7


def test_visualize(tmp_path):
    c = Computer()
    add_test_data(c)

    target = tmp_path / "visualize.png"

    # visualize() works
    c.visualize(str(target))

    assert target.exists()

    # TODO compare to a specimen

import logging

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
from genno.testing import assert_qty_equal


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


def test_get_comp():
    # Invalid name for a function returns None
    assert Computer()._get_comp(42) is None


def test_require_compat():
    c = Computer()
    with pytest.raises(
        ModuleNotFoundError,
        match="No module named '_test', required by genno.compat._test",
    ):
        c._require_compat("_test")


def test_add():
    """Adding computations that refer to missing keys raises KeyError."""
    r = Computer()
    r.add("a", 3)
    r.add("d", 4)

    # Invalid: value before key
    with pytest.raises(TypeError):
        r.add(42, "a")

    # Adding an existing key with strict=True
    with pytest.raises(KeyExistsError, match=r"key 'a' already exists"):
        r.add("a", 5, strict=True)

    def gen(other):  # pragma: no cover
        """A generator for apply()."""
        return (lambda a, b: a * b, "a", other)

    def msg(*keys):
        """Return a regex for str(MissingKeyError(*keys))."""
        return f"required keys {repr(tuple(keys))} not defined".replace(
            "(", "\\("
        ).replace(")", "\\)")

    # One missing key
    with pytest.raises(MissingKeyError, match=msg("b")):
        r.add_product("ab", "a", "b")

    # Two missing keys
    with pytest.raises(MissingKeyError, match=msg("c", "b")):
        r.add_product("abc", "c", "a", "b")

    # Using apply() targeted at non-existent keys also raises an Exception
    with pytest.raises(MissingKeyError, match=msg("e", "f")):
        r.apply(gen, "d", "e", "f")

    # add(..., strict=True) checks str or Key arguments
    g = Key("g", "hi")
    with pytest.raises(MissingKeyError, match=msg("b", g)):
        r.add("foo", (computations.product, "a", "b", g), strict=True)

    # aggregate() and disaggregate() call add(), which raises the exception
    with pytest.raises(MissingKeyError, match=msg(g)):
        r.aggregate(g, "tag", "i")
    with pytest.raises(MissingKeyError, match=msg(g)):
        r.disaggregate(g, "j")

    # add(..., sums=True) also adds partial sums
    r.add("foo:a-b-c", [], sums=True)
    assert "foo:b" in r

    # add(name, ...) where name is the name of a computation
    r.add("select", "bar", "a", indexers={"dim": ["d0", "d1", "d2"]})

    # add(name, ...) with keyword arguments not recognized by the computation
    # raises an exception
    msg = "unexpected keyword argument 'bad_kwarg'"
    with pytest.raises(TypeError, match=msg):
        r.add("select", "bar", "a", bad_kwarg="foo", index=True)


def test_add_queue(caplog):
    r = Computer()
    r.add("foo-0", (lambda x: x, 42))

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
        r.add(queue, max_tries=3, fail="raise")

    # But foo-2 was successfully added on the second pass, and gives the
    # correct result
    assert r.get("foo-2") == 42 * 10 * 10

    # Failures without raising an exception
    r.add(queue, max_tries=3, fail=logging.INFO)
    assert "Failed 3 times to add:" in caplog.messages
    assert "    with KeyExistsError('foo-2')" in caplog.messages


def test_apply():
    # Reporter with two scalar values
    r = Computer()
    r.add("foo", (lambda x: x, 42))
    r.add("bar", (lambda x: x, 11))

    N = len(r.keys())

    # A computation
    def _product(a, b):
        return a * b

    # A generator function that yields keys and computations
    def baz_qux(key):
        yield key + ":baz", (_product, key, 0.5)
        yield key + ":qux", (_product, key, 1.1)

    # Apply the generator to two targets
    r.apply(baz_qux, "foo")
    r.apply(baz_qux, "bar")

    # Four computations were added to the reporter
    N += 4
    assert len(r.keys()) == N
    assert r.get("foo:baz") == 42 * 0.5
    assert r.get("foo:qux") == 42 * 1.1
    assert r.get("bar:baz") == 11 * 0.5
    assert r.get("bar:qux") == 11 * 1.1

    # A generator that takes two arguments
    def twoarg(key1, key2):
        yield key1 + "__" + key2, (_product, key1, key2)

    r.apply(twoarg, "foo:baz", "bar:qux")

    # One computation added to the reporter
    N += 1
    assert len(r.keys()) == N
    assert r.get("foo:baz__bar:qux") == 42 * 0.5 * 11 * 1.1

    # A useless generator that does nothing
    def useless():
        return

    r.apply(useless)

    # Also call via add()
    r.add("apply", useless)

    # Nothing added to the reporter
    assert len(r.keys()) == N

    # Adding with a generator that takes Reporter as the first argument
    def add_many(rep: Computer, max=5):
        [rep.add(f"foo{x}", _product, "foo", x) for x in range(max)]

    r.apply(add_many, max=10)

    # Function was called, adding keys
    assert len(r.keys()) == N + 10

    # Keys work
    assert r.get("foo9") == 42 * 9


def test_disaggregate():
    r = Computer()
    foo = Key("foo", ["a", "b", "c"])
    r.add(foo, "<foo data>")
    r.add("d_shares", "<share data>")

    # Disaggregation works
    r.disaggregate(foo, "d", args=["d_shares"])

    assert "foo:a-b-c-d" in r.graph
    assert r.graph["foo:a-b-c-d"] == (
        computations.disaggregate_shares,
        "foo:a-b-c",
        "d_shares",
    )

    # Invalid method
    with pytest.raises(ValueError):
        r.disaggregate(foo, "d", method="baz")

    with pytest.raises(TypeError):
        r.disaggregate(foo, "d", method=None)


def test_file_io(tmp_path):
    r = Computer()

    # Path to a temporary file
    p = tmp_path / "foo.txt"

    # File can be added to the Reporter before it is created, because the file
    # is not read until/unless required
    k1 = r.add_file(p)

    # File has the expected key
    assert k1 == "file:foo.txt"

    # Add some contents to the file
    p.write_text("Hello, world!")

    # The file's contents can be read through the Reporter
    assert r.get("file:foo.txt") == "Hello, world!"

    # Write the report to file
    p2 = tmp_path / "bar.txt"
    r.write("file:foo.txt", p2)

    # Write using a string path
    r.write("file:foo.txt", str(p2))

    # The Reporter produces the expected output file
    assert p2.read_text() == "Hello, world!"


def test_file_formats(test_data_path, tmp_path):
    r = Computer()

    expected = Quantity(
        pd.read_csv(test_data_path / "input0.csv", index_col=["i", "j"])["value"],
        units="km",
    )

    # CSV file is automatically parsed to xr.DataArray
    p1 = test_data_path / "input0.csv"
    k = r.add_file(p1, units=pint.Unit("km"))
    assert_qty_equal(r.get(k), expected)

    # Dimensions can be specified
    p2 = test_data_path / "input1.csv"
    k2 = r.add_file(p2, dims=dict(i="i", j_dim="j"))
    assert_qty_equal(r.get(k), r.get(k2))

    # Units are loaded from a column
    assert r.get(k2).attrs["_unit"] == pint.Unit("km")

    # Specifying units that do not match file contents → ComputationError
    r.add_file(p2, key="bad", dims=dict(i="i", j_dim="j"), units="kg")
    with pytest.raises(ComputationError):
        r.get("bad")

    # Write to CSV
    p3 = tmp_path / "output.csv"
    r.write(k, p3)

    # Output is identical to input file, except for order
    assert sorted(p1.read_text().split("\n")) == sorted(p3.read_text().split("\n"))

    # Write to Excel
    p4 = tmp_path / "output.xlsx"
    r.write(k, p4)
    # TODO check the contents of the Excel file


def test_full_key():
    r = Computer()

    # Without index, the full key cannot be retrieved
    r.add("a:i-j-k", [])
    with pytest.raises(KeyError, match="a"):
        r.full_key("a")

    # Using index=True adds the full key to the index
    r.add("a:i-j-k", [], index=True)
    assert r.full_key("a") == "a:i-j-k"

    # The full key can be retrieved by giving only some of the indices
    assert r.full_key("a:j") == "a:i-j-k"

    # Same with a tag
    r.add("a:i-j-k:foo", [], index=True)
    # Original and tagged key can both be retrieved
    assert r.full_key("a") == "a:i-j-k"
    assert r.full_key("a::foo") == "a:i-j-k:foo"


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

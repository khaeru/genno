import pytest

from genno import Key
from genno.core.key import iter_keys, single_key


def test_key():
    k1 = Key("foo", ["a", "b", "c"])
    k2 = Key("bar", ["d", "c", "b"])

    # String
    assert str(k1) == "foo:a-b-c"

    # Representation
    assert repr(k1) == "<foo:a-b-c>"

    # Key hashes the same as its string representation
    assert hash(k1) == hash("foo:a-b-c")

    # Key compares equal to its string representation
    assert k1 == "foo:a-b-c"

    # product:
    assert Key.product("baz", k1, k2) == Key("baz", ["a", "b", "c", "d"])
    assert Key.product("baz", str(k1), str(k2)) == Key("baz", ["a", "b", "c", "d"])

    # iter_sums: Number of partial sums for a 3-dimensional quantity
    assert sum(1 for a in k1.iter_sums()) == 7

    # Key with name and tag but no dimensions
    assert Key("foo", tag="baz") == "foo::baz"


_invalid = pytest.mark.xfail(raises=ValueError, reason="Invalid key expression")


CASES = (
    ("foo", Key("foo")),
    ("foo:", Key("foo")),
    ("foo::", Key("foo")),
    ("foo::bar", Key("foo", tag="bar")),
    ("foo::bar+baz", Key("foo", tag="bar+baz")),
    ("foo:a-b", Key("foo", "ab")),
    ("foo:a-b:", Key("foo", "ab")),
    ("foo:a-b:bar", Key("foo", "ab", "bar")),
    # Weird but not invalid
    ("foo::++", Key("foo", tag="++")),
    # Invalid
    pytest.param(":", None, marks=_invalid),
    pytest.param("::", None, marks=_invalid),
    pytest.param("::bar", None, marks=_invalid),
    pytest.param(":a-b:bar", None, marks=_invalid),
    pytest.param("foo:a-b-", None, marks=_invalid),
    # Bad arguments
    pytest.param(42.1, None, marks=pytest.mark.xfail(raises=TypeError)),
)


class TestKey:
    @pytest.mark.parametrize("value, expected", CASES)
    def test_init0(self, value, expected):
        assert expected == Key(value)

    @pytest.mark.parametrize(
        "args, expected",
        (
            ((Key("foo:a-b-c"), [], "t2"), Key("foo:a-b-c:t2")),
            pytest.param(
                (Key("foo:a-b-c:t1"), [], "t2"),
                None,
                marks=pytest.mark.xfail(raises=ValueError),
            ),
            pytest.param(
                (Key("foo:a-b-c"), "d e f".split()),
                None,
                marks=pytest.mark.xfail(raises=ValueError),
            ),
        ),
    )
    def test_init1(self, args, expected):
        assert expected == Key(*args)

    @pytest.mark.parametrize("value, expected", CASES)
    def test_from_str_or_key0(self, value, expected):
        with pytest.warns(FutureWarning, match="no longer necessary"):
            assert expected == Key.from_str_or_key(value)

    @pytest.mark.parametrize(
        "kwargs, value, expected",
        (
            (dict(drop="b"), "foo:a-b-c", Key("foo:a-c")),
            (dict(drop="b", append="d"), "foo:a-b-c", Key("foo:a-c-d")),
            (dict(drop="b", tag="t2"), "foo:a-b-c:t1", Key("foo:a-c:t1+t2")),
        ),
    )
    def test_from_str_or_key1(self, kwargs, value, expected):
        assert expected == Key.from_str_or_key(value, **kwargs)

    def test_drop(self):
        key = Key("out:nl-t-yv-ya-m-nd-c-l-h-hd")
        assert "out:t-yv-ya-c-l" == key.drop("h", "hd", "m", "nd", "nl")

    def test_operations(self):
        key = Key("x:a-b-c")

        # __add__: Add a tag
        assert "x:a-b-c:foo" == key + "foo"
        # Associative: (key + "foo") is another key that supports __add__
        assert "x:a-b-c:foo+bar" == key + "foo" + "bar"

        # __mul__: add a dimension
        assert "x:a-b-c-d" == key * "d"

        # Existing dimension → no change
        assert key == key * "c"

        # __truediv__: drop a dimension
        assert "x:a-c" == key / "b"

        # Invalid
        with pytest.raises(TypeError):
            key + 1.1
        with pytest.raises(TypeError):
            key * 2.2
        with pytest.raises(TypeError):
            key / 3.3


def test_sorted():
    k1 = Key("foo", "abc")
    k2 = Key("foo", "cba")

    # Keys with same dimensions, ordered differently, compare equal
    assert k1 == k2

    # Ordered returns a key with sorted dimensions
    assert k1.dims == k2.sorted.dims

    # Keys compare equal to an equivalent string and to one another
    assert k1 == "foo:b-a-c" == k2 == "foo:b-c-a"

    # Keys do not hash equal
    assert hash(k1) == hash("foo:a-b-c")
    assert hash(k2) == hash("foo:c-b-a")
    assert hash(k1) != hash(k2)


def test_gt_lt():
    """Test :meth:`Key.__gt__` and :meth:`Key.__lt__`."""
    k = Key("foo", "abd")
    assert k > "foo:a-b-c"
    assert k > Key("foo", "abc")
    assert k < "foo:a-b-e"
    assert k < Key("foo", "abe")

    # Comparison with other types not supported
    with pytest.raises(TypeError):
        assert k < 1.1

    with pytest.raises(TypeError):
        assert k > 1.1


def test_iter_keys():
    # Non-iterable
    with pytest.raises(TypeError):
        next(iter_keys(1.2))

    # Iterable containing non-keys
    with pytest.raises(TypeError):
        list(iter_keys([Key("a"), Key("b"), 1.2]))


def test_single_key():
    # Single key is unpacked
    k = Key("a")
    result = single_key((k,))
    assert k is result

    # Tuple containing 1 non-key
    with pytest.raises(TypeError):
        single_key((1.2,))

    # Tuple containing >1 Keys
    with pytest.raises(TypeError):
        single_key((k, k))

    # Empty iterable
    with pytest.raises(TypeError):
        single_key([])

import pytest

from genno import Key


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

    # iter_sums: Number of partial sums for a 3-dimensional quantity
    assert sum(1 for a in k1.iter_sums()) == 7

    # Key with name and tag but no dimensions
    assert Key("foo", tag="baz") == "foo::baz"


_invalid = pytest.mark.xfail(raises=ValueError, reason="Invalid key expression")


@pytest.mark.parametrize(
    "value, expected",
    [
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
    ],
)
def test_from_str(value, expected):
    assert expected == Key.from_str_or_key(value)


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

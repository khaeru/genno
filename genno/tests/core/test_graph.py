import pytest

from genno import Key
from genno.core.graph import Graph


class TestGraph:
    @pytest.fixture
    def g(self):
        g = Graph()
        g["foo:c-b-a"] = 1
        yield g

    def test_delitem(self, g):
        assert Key("foo", "cba") == g.full_key("foo")
        del g["foo:c-b-a"]
        assert None is g.full_key("foo")

    def test_infer(self, g):
        g["foo:x-y-z:bar"] = 2
        g["config"] = dict(baz="qux")

        # Correct result for str or Key argument
        assert "foo:c-b-a" == g.infer("foo")
        assert "foo:c-b-a" == g.infer(Key("foo"))

        # Correct result for str or Key argument with tag
        assert "foo:x-y-z:bar" == g.infer("foo::bar")
        assert "foo:x-y-z:bar" == g.infer(Key("foo", tag="bar"))

        # String passes through
        for k in ("config", "baz"):
            result = g.infer(k)
            assert isinstance(result, str) and k == result

    def test_pop(self, g):
        assert Key("foo", "cba") == g.full_key("foo")
        assert 1 == g.pop("foo:c-b-a")
        assert None is g.full_key("foo")

    def test_setitem(self, g):
        g[Key("baz", "cba")] = 2

        assert Key("baz", "cba") == g.unsorted_key(Key("baz", "cab"))

    def test_update(self, g):
        g.update([("foo:y-x", 1), ("bar:m-n", 2)])
        assert Key("bar", "mn") == g.full_key("bar")

        g.update(baz=3)
        assert Key("baz") == g.unsorted_key("baz")

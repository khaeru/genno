import pytest
from sdmx.model.common import Code, Codelist

from genno import Computer
from genno.compat.sdmx import codelist_to_groups
from genno.testing import add_test_data


def test_codelist_to_groups() -> None:
    c = Computer()
    _, t_foo, t_bar, __ = add_test_data(c)

    cl: Codelist = Codelist(id="t")
    cl.append(Code(id="foo", child=[Code(id=t) for t in t_foo]))
    cl.append(Code(id="bar", child=[Code(id=t) for t in t_bar]))

    # Operator runs
    for result0 in (
        codelist_to_groups(cl),
        codelist_to_groups(iter(cl), dim="t"),
    ):
        # Result has the expected contents
        assert {"t"} == set(result0.keys())
        result_t = result0["t"]
        assert {"foo", "bar"} == set(result_t.keys())
        assert set(t_foo) == set(result_t["foo"])
        assert set(t_bar) == set(result_t["bar"])

    with pytest.raises(ValueError, match="Must provide a dimension"):
        codelist_to_groups(iter(cl))

    # Output is usable in Computer() with aggregate
    c.require_compat("genno.compat.sdmx")
    c.add("t::codes", cl)
    c.add("t::groups", "codelist_to_groups", "t::codes")
    key = c.add("x::agg", "aggregate", "x:t-y", "t::groups", False)

    result1 = c.get(key)

    # Quantity was aggregated per `cl`
    assert {"foo", "bar"} == set(result1.coords["t"].data)

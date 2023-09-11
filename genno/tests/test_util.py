import logging
import re

import pandas as pd
import pint
import pytest
from dask.core import quote

from genno import Key, Quantity
from genno.compat.pint import PintError
from genno.testing import assert_logs
from genno.util import (
    clean_units,
    collect_units,
    filter_concat_args,
    parse_units,
    partial_split,
    unquote,
)


@pytest.mark.parametrize("input, exp", (("[kg]", "kg"), ("%", "percent")))
def test_clean_units(input, exp):
    assert exp == clean_units(input)


def test_collect_units(caplog, ureg):
    q1 = Quantity(pd.Series([42, 43]), units="kg")
    # Force string units
    q1.attrs["_unit"] = "kg"

    # Units are converted to pint.Unit
    assert (ureg.kg,) == collect_units(q1)

    q2 = Quantity(pd.Series([42, 43]), name="foo")
    with caplog.at_level(logging.DEBUG):
        assert (ureg.dimensionless,) == collect_units(q2)
    assert (
        "AttrSeries 'foo' ('dim_0',) lacks units; assume dimensionless"
        == caplog.messages[-1]
    )

    assert (ureg.dimensionless,) == collect_units(1.0)

    # with pytest.raises(FileNotFoundError):
    collect_units(object())


def test_filter_concat_args(caplog):
    with assert_logs(
        caplog,
        [
            "concat() argument 'key1' missing; will be omitted",
            "concat() argument <foo:x-y-z> missing; will be omitted",
        ],
    ):
        result = list(
            filter_concat_args(
                ["key1", Quantity(pd.Series([42, 43]), units="kg"), Key("foo", "xyz")]
            )
        )

    assert len(result) == 1


msg = "unit '{}' cannot be parsed; contains invalid character(s) '{}'"


@pytest.mark.parametrize(
    "input, expected",
    (
        # Mixed units
        (["kg", "km"], (ValueError, re.escape("mixed units ['kg', 'km']"))),
        (["kg", "kg"], "kg"),
        # Units with / are defined
        (["foo/bar"], "foo/bar"),
        # Dimensionless
        ([], "dimensionless"),
        # Invalid characters, alone or with prefix
        # NB match=re.escape(msg.format("_?", "?") in pint 0.20, but varies in pint 0.17
        (["_?"], ((ValueError, pint.UndefinedUnitError), None)),
        # NB match=re.escape(msg.format("E$", "$") in pint 0.20, but varies in pint 0.17
        (["E$"], ((ValueError, pint.UndefinedUnitError), None)),
        (["kg-km"], (ValueError, re.escape(msg.format("kg-km", "-")))),
    ),
    ids=lambda argvalue: repr(argvalue),
)
def test_parse_units0(ureg, input, expected):
    if isinstance(expected, str):
        # Expected to work
        result = parse_units(input, ureg)
        assert ureg.parse_units(expected) == result
    else:
        # Expected to raise an exception
        with pytest.raises(expected[0], match=expected[1]):
            parse_units(pd.Series(input))


def test_parse_units1(ureg, caplog):
    """Multiple attempts to (re)define new units."""
    parse_units("JPY")
    parse_units("GBP/JPY")

    with pytest.raises(PintError, match="cannot be parsed; contains invalid character"):
        parse_units("GBP/JPY/$?")


def test_partial_split():
    # Function with ordinary arguments
    def func1(arg1, arg2, foo=-1, bar=-1):
        pass  # pragma: no cover

    # Function with keyword-only arguments
    def func2(arg1, arg2, *, foo, bar):
        pass  # pragma: no cover

    kwargs = dict(arg1=0, foo=1, bar=2, baz=3)

    _, extra = partial_split(func1, kwargs)
    assert {"baz"} == set(extra.keys())

    _, extra = partial_split(func2, kwargs)
    assert {"baz"} == set(extra.keys())

    with pytest.raises(TypeError):
        partial_split(1.2, kwargs)


@pytest.mark.parametrize(
    "value, exp",
    (
        # Quotable values are unwrapped
        (quote(dict(foo="bar")), dict(foo="bar")),
        (quote(["hello", "world"]), ["hello", "world"]),
        # No effect on others
        (42.0, 42.0),
    ),
)
def test_unquote(value, exp):
    assert exp == unquote(value)

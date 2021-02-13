import re

import pandas as pd
import pytest
from dask.core import quote

from genno import Key, Quantity
from genno.testing import assert_logs
from genno.util import (
    clean_units,
    collect_units,
    filter_concat_args,
    parse_units,
    unquote,
)


@pytest.mark.parametrize("input, exp", (("[kg]", "kg"), ("%", "percent")))
def test_clean_units(input, exp):
    assert exp == clean_units(input)


def test_collect_units(ureg):
    q1 = Quantity(pd.Series([42, 43]), units="kg")
    # Force string units
    q1.attrs["_unit"] = "kg"

    # Units are converted to pint.Unit
    assert (ureg.kg,) == collect_units(q1)


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
        (["_?"], (ValueError, re.escape(msg.format("_?", "?")))),
        (["E$"], (ValueError, re.escape(msg.format("E$", "$")))),
        (["kg-km"], (ValueError, re.escape(msg.format("kg-km", "-")))),
    ),
    ids=lambda argvalue: repr(argvalue),
)
def test_parse_units(ureg, input, expected):
    if isinstance(expected, str):
        # Expected to work
        result = parse_units(input, ureg)
        assert ureg.parse_units(expected) == result
    else:
        # Expected to raise an exception
        with pytest.raises(expected[0], match=expected[1]):
            parse_units(pd.Series(input))


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

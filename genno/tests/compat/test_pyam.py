import logging
from collections import namedtuple
from functools import partial

import pandas as pd
import pytest

from pandas.testing import assert_frame_equal, assert_series_equal

from genno import Computer, Key
from genno.computations import load_file
from genno.compat.pyam import computations


# Skip this entire file if pyam is not installed
pyam = pytest.importorskip("pyam", reason="pyam-iamc not installed")


@pytest.fixture(scope="session")
def scenario():
    """Mock object which resembles ixmp.Scenario."""
    Scenario = namedtuple("Scenario", ["model", "scenario"])
    yield Scenario(model="Canning problem (MESSAGE scheme)", scenario="standard")


@pytest.fixture(scope="session")
def dantzig_reporter(test_data_path, scenario, ureg):
    """Computer with minimal contents for below tests."""
    # TODO complete:
    # - Create the quantities used by test_concat().

    ureg.define("USD = [money]")
    ureg.define("case = [case]")

    c = Computer()

    for name, units in (("ACT", ""), ("var_cost", "USD/case")):
        qty = load_file(test_data_path / f"dantzig-{name}.csv", name=name, units=units)
        c.add(Key(name, qty.dims), qty, index=True)

    c.add("scenario", scenario)

    yield c


def test_as_pyam(dantzig_reporter, scenario):
    rep = dantzig_reporter

    # Quantities for 'ACT' variable at full resolution
    qty = rep.get(rep.full_key("ACT"))

    # Call as_pyam() with an empty quantity
    p = computations.as_pyam(scenario, qty[0:0], year_time_dim="ya")
    assert isinstance(p, pyam.IamDataFrame)


def test_convert_pyam(dantzig_reporter, caplog, tmp_path, test_data_path):
    rep = dantzig_reporter

    # Key for 'ACT' variable at full resolution
    ACT = rep.full_key("ACT")

    # Add a computation that converts ACT to a pyam.IamDataFrame
    rep.add(
        "ACT IAMC",
        (
            partial(computations.as_pyam, drop=["yv"], year_time_dim="ya"),
            "scenario",
            ACT,
        ),
    )

    # Result is an IamDataFrame
    idf1 = rep.get("ACT IAMC")
    assert isinstance(idf1, pyam.IamDataFrame)

    # …of expected length
    assert len(idf1) == 8

    # …in which variables are not renamed
    assert idf1["variable"].unique() == "ACT"

    # Warning was logged because of extra columns
    assert (
        "genno.compat.pyam.computations",
        logging.WARNING,
        "Extra columns ['h', 'm', 't'] when converting 'ACT' to IAMC format",
    ) in caplog.record_tuples

    # Repeat, using the message_ix.Reporter convenience function
    def add_tm(df, name="Activity"):
        """Callback for collapsing ACT columns."""
        df["variable"] = f"{name}|" + df["t"] + "|" + df["m"]
        return df.drop(["t", "m"], axis=1)

    # Use the convenience function to add the node
    keys = rep.convert_pyam(ACT, "ya", collapse=add_tm)

    # Keys of added node(s) are returned
    assert len(keys) == 1
    key2, *_ = keys
    assert key2 == ACT.name + ":iamc"

    caplog.clear()

    # Result
    idf2 = rep.get(key2)
    df2 = idf2.as_pandas()

    # Extra columns have been removed:
    # - m and t by the collapse callback.
    # - h automatically, because 'ya' was used for the year index.
    assert not any(c in df2.columns for c in ["h", "m", "t"])

    # Variable names were formatted by the callback
    reg_var = pd.DataFrame(
        [
            ["san-diego", "Activity|canning_plant|production"],
            ["san-diego", "Activity|transport_from_san-diego|to_chicago"],
            ["san-diego", "Activity|transport_from_san-diego|to_new-york"],
            ["san-diego", "Activity|transport_from_san-diego|to_topeka"],
            ["seattle", "Activity|canning_plant|production"],
            ["seattle", "Activity|transport_from_seattle|to_chicago"],
            ["seattle", "Activity|transport_from_seattle|to_new-york"],
            ["seattle", "Activity|transport_from_seattle|to_topeka"],
        ],
        columns=["region", "variable"],
    )
    assert_frame_equal(df2[["region", "variable"]], reg_var)

    # message_ix.Reporter uses pyam.IamDataFrame.to_csv() to write to file
    path = tmp_path / "activity.csv"
    rep.write(key2, path)

    # File contents are as expected
    assert test_data_path.joinpath("pyam-write.csv").read_text() == path.read_text()

    # Use a name map to replace variable names
    rep.add("activity variables", {"Activity|canning_plant|production": "Foo"})
    key3 = rep.convert_pyam(
        ACT, "ya", replace_vars="activity variables", collapse=add_tm
    ).pop()
    df3 = rep.get(key3).as_pandas()

    # Values are the same; different names
    exp = df2[df2.variable == "Activity|canning_plant|production"][
        "value"
    ].reset_index()
    assert all(exp == df3[df3.variable == "Foo"]["value"].reset_index())

    # Now convert variable cost
    cb = partial(add_tm, name="Variable cost")
    key4 = rep.convert_pyam("var_cost", "ya", collapse=cb).pop()
    df4 = rep.get(key4).as_pandas().drop(["model", "scenario"], axis=1)

    # Results have the expected units
    assert all(df4["unit"] == "USD / case")

    # Also change units
    key5 = rep.convert_pyam("var_cost", "ya", collapse=cb, unit="centiUSD / case").pop()
    df5 = rep.get(key5).as_pandas().drop(["model", "scenario"], axis=1)

    # Results have the expected units
    assert all(df5["unit"] == "centiUSD / case")
    assert_series_equal(df4["value"], df5["value"] / 100.0)


def test_concat(dantzig_reporter):
    """pyam.concat() correctly passes through to ixmp…concat()."""
    rep = dantzig_reporter

    key = rep.add(
        "test",
        computations.concat,
        "fom:nl-t-ya",
        "vom:nl-t-ya",
        "tom:nl-t-ya",
    )
    rep.get(key)

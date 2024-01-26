import pytest
import sdmx
from sdmx.format import Version
from sdmx.model.common import Code, Codelist

import genno.operator
from genno import Computer
from genno.compat.sdmx import operator
from genno.testing import add_test_data


def test_codelist_to_groups() -> None:
    c = Computer()
    _, t_foo, t_bar, __ = add_test_data(c)

    cl: Codelist = Codelist(id="t")
    cl.append(Code(id="foo", child=[Code(id=t) for t in t_foo]))
    cl.append(Code(id="bar", child=[Code(id=t) for t in t_bar]))

    # Operator runs
    for result0 in (
        operator.codelist_to_groups(cl),
        operator.codelist_to_groups(iter(cl), dim="t"),
    ):
        # Result has the expected contents
        assert {"t"} == set(result0.keys())
        result_t = result0["t"]
        assert {"foo", "bar"} == set(result_t.keys())
        assert set(t_foo) == set(result_t["foo"])
        assert set(t_bar) == set(result_t["bar"])

    with pytest.raises(ValueError, match="Must provide a dimension"):
        operator.codelist_to_groups(iter(cl))

    # Output is usable in Computer() with aggregate
    c.require_compat("genno.compat.sdmx")
    c.add("t::codes", cl)
    c.add("t::groups", "codelist_to_groups", "t::codes")
    key = c.add("x::agg", "aggregate", "x:t-y", "t::groups", False)

    result1 = c.get(key)

    # Quantity was aggregated per `cl`
    assert {"foo", "bar"} == set(result1.coords["t"].data)


@pytest.fixture(scope="session")
def dsd(test_data_path):
    # Read the data structure definition
    yield sdmx.read_sdmx(test_data_path.joinpath("22_289-structure.xml")).structure[
        "DCIS_POPRES1"
    ]


@pytest.fixture(scope="session")
def dm(test_data_path, dsd):
    # Read the data message
    yield sdmx.read_sdmx(test_data_path.joinpath("22_289.xml"), structure=dsd)


def test_dataset_to_quantity(dsd, dm) -> None:
    # Select the data set
    ds = dm.data[0]

    # Operator runs
    result = operator.dataset_to_quantity(ds)

    # Dimensions of the quantity match the dimensions of the data frame
    assert set(d.id for d in dsd.dimensions.components) == set(result.dims)

    # Attributes contain information on the data set and its structure
    assert (
        "urn:sdmx:org.sdmx.infomodel.datastructure.DataStructureDefinition="
        "IT1:DCIS_POPRES1(1.0)" == result.attrs["structure_urn"]
    )

    # All observations are converted
    assert len(ds.obs) == result.size


VERSION = (None, Version["2.1"], Version["3.0"], "2.1", "3.0")


@pytest.mark.parametrize("observation_dimension", (None, "TIME_PERIOD"))
@pytest.mark.parametrize("version", VERSION)
@pytest.mark.parametrize("with_attrs", (True, False))
def test_quantity_to_dataset(
    dsd, dm, observation_dimension, version, with_attrs
) -> None:
    ds = dm.data[0]
    qty = operator.dataset_to_quantity(ds)

    if not with_attrs:
        qty.attrs.pop("structure_urn")

    result = operator.quantity_to_dataset(
        qty, structure=dsd, observation_dimension=observation_dimension, version=version
    )

    # All observations are converted
    assert len(ds.obs) == len(result.obs)

    # Dataset is associated with its DSD
    assert dsd is result.structured_by


@pytest.mark.parametrize("observation_dimension", (None, "TIME_PERIOD"))
@pytest.mark.parametrize("version", VERSION)
def test_quantity_to_message(dsd, dm, observation_dimension, version) -> None:
    ds = dm.data[0]
    qty = operator.dataset_to_quantity(ds)

    header = dm.header

    result = operator.quantity_to_message(
        qty,
        structure=dsd,
        observation_dimension=observation_dimension,
        version=version,
        header=header,
    )

    # Currently False because OBS_STATUS attributes are not preserved
    with pytest.raises(AssertionError):
        # Resulting message compares equal to the original ("round trip")
        assert dm.compare(result)


@pytest.mark.parametrize("observation_dimension", (None, "TIME_PERIOD"))
@pytest.mark.parametrize(
    "version",
    (
        None,
        Version["2.1"],
        pytest.param(
            Version["3.0"],
            marks=pytest.mark.xfail(
                raises=NotImplementedError, reason="Not implemented in sdmx1"
            ),
        ),
        "2.1",
        pytest.param(
            "3.0",
            marks=pytest.mark.xfail(
                raises=NotImplementedError, reason="Not implemented in sdmx1"
            ),
        ),
    ),
)
def test_write_report(tmp_path, dsd, dm, observation_dimension, version) -> None:
    ds = dm.data[0]
    qty = operator.dataset_to_quantity(ds)

    header = dm.header

    obj = operator.quantity_to_message(
        qty,
        structure=dsd,
        observation_dimension=observation_dimension,
        version=version,
        header=header,
    )

    path = tmp_path.joinpath("foo.xml")

    genno.operator.write_report(obj, path)

    print(f"{path.read_text() = }")

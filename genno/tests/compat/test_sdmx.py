import pytest
import sdmx
from sdmx.model.common import Code, Codelist

from genno import Computer
from genno.compat.sdmx import (
    codelist_to_groups,
    dataset_to_quantity,
    quantity_to_dataset,
)
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


def test_dataset_to_quantity(dsd, dm):
    # Select the data set
    ds = dm.data[0]

    # Operator runs
    result = dataset_to_quantity(ds)

    # Dimensions of the quantity match the dimensions of the data frame
    assert set(d.id for d in dsd.dimensions.components) == set(result.dims)

    # Attributes contain information on the data set and its structure
    assert (
        "urn:sdmx:org.sdmx.infomodel.datastructure.DataStructureDefinition="
        "IT1:DCIS_POPRES1(1.0)" == result.attrs["structure_urn"]
    )

    # All observations are converted
    assert len(ds.obs) == result.size


def test_quantity_to_dataset(dsd, dm):
    ds = dm.data[0]
    qty = dataset_to_quantity(ds)

    result = quantity_to_dataset(qty, structure=dsd)

    # All observations are converted
    assert len(ds.obs) == len(result.obs)

    # Dataset is associated with its DSD
    assert dsd is ds.structured_by

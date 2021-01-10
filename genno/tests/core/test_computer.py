import xarray as xr

from genno import Computer, Quantity, computations


def test_units(ureg):
    """Test handling of units within Reporter computations."""
    r = Computer()

    # Create some dummy data
    dims = dict(coords=["a b c".split()], dims=["x"])
    r.add("energy:x", Quantity(xr.DataArray([1.0, 3, 8], **dims), units="MJ"))
    r.add("time", Quantity(xr.DataArray([5.0, 6, 8], **dims), units="hour"))
    r.add("efficiency", Quantity(xr.DataArray([0.9, 0.8, 0.95], **dims)))

    # Aggregation preserves units
    r.add("energy", (computations.sum, "energy:x", None, ["x"]))
    assert r.get("energy").attrs["_unit"] == ureg.parse_units("MJ")

    # Units are derived for a ratio of two quantities
    r.add("power", (computations.ratio, "energy:x", "time"))
    assert r.get("power").attrs["_unit"] == ureg.parse_units("MJ/hour")

    # Product of dimensioned and dimensionless quantities keeps the former
    r.add("energy2", (computations.product, "energy:x", "efficiency"))
    assert r.get("energy2").attrs["_unit"] == ureg.parse_units("MJ")

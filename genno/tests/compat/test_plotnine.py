from pathlib import Path

import plotnine as p9
import pytest
import xarray as xr

from genno import Computer, Quantity
from genno.compat.plotnine import Plot


def test_Plot(tmp_path):
    c = Computer(output_dir=tmp_path)
    t = [("t", [-1, 0, 1])]
    c.add("x:t", Quantity(xr.DataArray([1.0, 2, 3], coords=t), name="x"))
    c.add("y:t", Quantity(xr.DataArray([1.0, 2, 3], coords=t), name="y"))

    # Exception raised when the class is incomplete
    with pytest.raises(
        TypeError,
        match=("Can't instantiate abstract class Plot1 with abstract methods generate"),
    ):

        class Plot1(Plot):
            inputs = ["x:t", "y:t"]

        c.add("plot", Plot1.make_task())

    class Plot2(Plot):
        basename = "test"
        suffix = ".svg"

        def generate(self, x, y):
            return p9.ggplot(x.merge(y, on="t"), p9.aes(x="x", y="y")) + p9.geom_point()

    c.add("plot", Plot2.make_task("x:t", "y:t"))

    # Graph contains the task. Don't compare the callable
    assert ("config", "x:t", "y:t") == c.graph["plot"][1:]
    assert callable(c.graph["plot"][0])

    # Plot can be generated
    result = c.get("plot")

    # Result is the path to the file
    assert isinstance(result, Path)

    # Concrete Plot subclasses can be further subclassed
    class Plot3(Plot2):
        suffix = ".pdf"
        inputs = ["x:t", "y:t"]

        def generate(self, x, y):
            # Return an iterable of 2 plots
            return (super().generate(x, y), super().generate(x, y))

    # Multi-page PDFs can be saved
    c.add("plot", Plot3.make_task())
    c.get("plot")

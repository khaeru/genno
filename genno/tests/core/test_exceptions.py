import re

from genno import ComputationError, Computer
from genno.testing import assert_logs
from genno.testing.jupyter import get_cell_output, run_notebook


def test_computationerror():
    """ComputationError._format() works in the context of a failed computation."""
    c = Computer()

    def func(x):
        return "a" + x

    c.add("test", func, 1.0)

    try:
        c.get("test")
    except ComputationError as e:
        r = str(e)

    assert re.match("computing 'test' using.*TypeError", r, flags=re.DOTALL)


def test_computationerror_format(caplog):
    """Test failures in ComputationError._format."""
    ce_none = ComputationError(None)

    msg = (
        "Exception raised while formatting None:\nAttributeError"
        "(\"'NoneType' object has no attribute '__traceback__'\")"
    )
    with assert_logs(caplog, msg):
        str(ce_none)


EXPECTED = re.compile(
    r"""computing 'test' using:

\(<function fail at \w+>,\)

Use Computer.describe\(...\) to trace the computation\.

Computation traceback:
  File ".*", line 4, in fail
    'x' \+ 3.4  # Raises TypeError(\n.*)?
TypeError: can only concatenate str \(not "float"\) to str.*"""
)


def test_computationerror_ipython(test_data_path, tmp_path):
    # NB this requires nbformat >= 5.0, because the output kind "evalue" was
    #    different pre-5.0
    fname = test_data_path / "exceptions.ipynb"
    nb, _ = run_notebook(fname, tmp_path, allow_errors=True)

    observed = get_cell_output(nb, 0, kind="evalue")
    assert EXPECTED.match(observed), observed

import re

from ixmp.testing import get_cell_output, run_notebook

from genno import ComputationError
from genno.testing import assert_logs


def test_computationerror(caplog):
    ce_none = ComputationError(None)

    # Message ends with ',)' on Python 3.6, only ')' on Python 3.7
    msg = (
        "Exception raised while formatting None:\nAttributeError"
        "(\"'NoneType' object has no attribute '__traceback__'\""
    )
    with assert_logs(caplog, msg):
        str(ce_none)


# The TypeError message differs:
# - Python 3.6: "must be str, not float"
# - Python 3.7: "can only concatenate str (not "float") to str"
EXPECTED = re.compile(
    r"""computing 'test' using:

\(<function fail at \w+>,\)

Use Computer.describe\(...\) to trace the computation.

Computation traceback:
  File "(<ipython-input-\d*-\w+>|[^"]*\.py)", line 4, in fail
    'x' \+ 3.4  # Raises TypeError
TypeError: .*str.*float.*
"""
)


def test_computationerror_ipython(test_data_path, tmp_path):
    # NB this requires nbformat >= 5.0, because the output kind "evalue" was
    #    different pre-5.0
    fname = test_data_path / "exceptions.ipynb"
    nb, _ = run_notebook(fname, tmp_path, allow_errors=True)

    observed = get_cell_output(nb, 0, kind="evalue")
    assert EXPECTED.match(observed), observed

from genno import configure
from genno.util import REPLACE_UNITS


def test_configure_units(caplog):
    # Warning is logged on invalid definitions
    configure(units=dict(define="0 = [0] * %"))
    assert 1 == len(caplog.records) and "WARNING" == caplog.records[0].levelname

    # Unit replacements are stored
    configure(units=dict(replace={"foo": "bar"}))
    assert REPLACE_UNITS.pop("foo") == "bar"

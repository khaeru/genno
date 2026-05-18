from genno import Computer


def test_import_pyam() -> None:
    """:func:`.as_pyam` operator is available only if pyam itself is installed.

    Unlike the tests in :mod:`.test_pyam`, this test should pass regardless of whether
    or not pyam is installed.
    """

    # Name 'iamc' can be imported; as in e.g. message-ix-models
    from genno.compat.pyam import HAS_PYAM, iamc

    del iamc

    c = Computer()

    try:
        c.require_compat("pyam")
    except ModuleNotFoundError:
        pass  # Fails if HAS_PYAM is False

    # Try to retrieve the as_pyam() operator
    operator = c.get_operator("as_pyam")

    assert callable(operator) if HAS_PYAM else operator is None

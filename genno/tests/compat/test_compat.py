def test_import_pyam():
    """.compat.pyam.operator is populated only if pyam itself is installed.

    Unlike the tests in :mod:`.test_pyam`, this test should pass regardless of whether
    or not pyam is installed.
    """
    from genno.compat.pyam import HAS_PYAM, operator

    # Same value, either True or False
    assert HAS_PYAM is hasattr(operator, "as_pyam")

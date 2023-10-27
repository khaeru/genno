import pytest

from genno import Computer, Operator


def null():
    pass  # pragma: no cover


class TestOperator:
    def test_add_tasks(self) -> None:
        op = Operator.define()(null)

        c = Computer()
        with pytest.raises(NotImplementedError):
            op.add_tasks(c)

    def test_add_tasks_deprecated(self) -> None:
        # Deprecated call triggers a warning
        with pytest.warns(DeprecationWarning):
            op = Operator.define(null)

        c = Computer()
        with pytest.raises(NotImplementedError):
            # Type of `op` is not Operator, so mypy complains
            op.add_tasks(c)  # type: ignore [attr-defined]

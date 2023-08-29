import pytest

from genno import Computer, Operator


def null():
    pass  # pragma: no cover


class TestOperator:
    def test_add_tasks(self):
        op = Operator.define(null)

        c = Computer()
        with pytest.raises(NotImplementedError):
            op.add_tasks(c)

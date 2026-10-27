import pytest

from app.agents.tools import ToolError, calculate


def test_calculator_supports_arithmetic_without_eval() -> None:
    assert calculate("(12 + 9) * 2") == 42


def test_calculator_rejects_code_execution() -> None:
    with pytest.raises(ToolError):
        calculate("__import__('os').system('id')")
